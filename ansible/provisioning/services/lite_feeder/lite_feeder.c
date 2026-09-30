/*
 * lite_feeder: lightweight daemon that replaces the BDWatchdog atop pipeline run inside the containers
 *
 *   atop <interval> -a -P CPU,cpu,MEM,SWP,NET,PRC,PRM,PRD
 *     | MetricsFeeder/src/atop/atop_to_json.py | MetricsFeeder/src/pipelines/send_to_OpenTSDB.py
 *
 * It reads /proc directly and sends to OpenTSDB (/api/put) the same data points, with the same metric names,
 * tags, units, rounding and filters as that pipeline (BDWatchdog MetricsFeeder with atop 2.4.0):
 *
 *   PRC  proc.cpu.user, proc.cpu.kernel         (clock ticks per second)   tags host, pid, command
 *   PRM  proc.mem.virtual, proc.mem.resident    (MB)                       tags host, pid, command
 *   PRD  proc.disk.reads.mb, proc.disk.writes.mb (MB/s)                    tags host, pid, command
 *   CPU  sys.cpu.usage                          (%)                        tags host
 *   cpu  sys.cpu.kernel, sys.cpu.user, sys.cpu.idle, sys.cpu.wait (%)      tags host, core
 *   MEM  sys.mem.free (MB), sys.mem.usage (%)                              tags host
 *   SWP  sys.swap.free (MB)                                                tags host
 *   NET  sys.net.in.mb, sys.net.out.mb (Mbit/s), sys.net.usage (%)         tags host, device
 *
 * Differences with the original pipeline (none of them changes the data points):
 *   - samples are aligned to multiples of the interval (e.g., every second at x.000 s);
 *   - HTTP requests without gzip, split so that each body stays below MAX_BODY_BYTES (OpenTSDB rejects bodies that its
 *     HTTP decoder splits in chunks, i.e., above 8192 bytes); failed requests are retried once and the
 *     sample is dropped, instead of stopping after 3 consecutive failures.
 *
 * Usage: lite_feeder [-i interval] [-H opentsdb_host] [-P opentsdb_port] [-g groups] [-s] [-c count]
 *   -i  sampling interval in seconds (default 5, as atop in ServerlessYARN)
 *   -H/-P  OpenTSDB address (default: OPENTSDB_URL/OPENTSDB_PORT from $BDWATCHDOG_PATH/services_config.yml,
 *          or /opt/BDWatchdog/services_config.yml)
 *   -g  comma-separated groups (default CPU,cpu,MEM,SWP,NET,PRC,PRM,PRD)
 *   -s  print the JSON documents to stdout (one per line, as atop_to_json.py) instead of sending them
 *   -c  stop after this number of samples (default: run forever)
 *
 * Build: gcc -O2 -o lite_feeder lite_feeder.c
 */
#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <netdb.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define MAX_BODY_BYTES 8000  /* Netty (OpenTSDB) splits bodies above 8192 bytes in chunks, which are rejected */
#define MAX_CPUS 1024
#define MAX_IFS 64

typedef unsigned long long u64;

/* ------------------------------------------------------------------------------------------------ options */
static int interval = 5, to_stdout = 0;
static long max_samples = -1;
static char tsdb_host[256] = "", tsdb_port[16] = "";
static int g_CPU = 1, g_cpu = 1, g_MEM = 1, g_SWP = 1, g_NET = 1, g_PRC = 1, g_PRM = 1, g_PRD = 1;
static long hertz, pagesize;
static char host_tag[512];

static void log_err(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "[LITE FEEDER] ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
}

/* ------------------------------------------------------------------------------------------------ strings */
typedef struct { char *s; size_t len, cap; } sbuf;

static void sb_add(sbuf *b, const char *fmt, ...) {
    va_list ap;
    for (;;) {
        size_t room = b->cap - b->len;
        va_start(ap, fmt);
        int n = vsnprintf(b->s + b->len, room, fmt, ap);
        va_end(ap);
        if (n >= 0 && (size_t)n < room) { b->len += n; return; }
        b->cap = b->cap ? b->cap * 2 + n : 65536;
        b->s = realloc(b->s, b->cap);
    }
}

/* Replace all occurrences of 'from' by 'to' in s (in place, s has room for MAX 4096 chars) */
static void replace_all(char *s, size_t size, const char *from, const char *to) {
    char out[4096];
    size_t fl = strlen(from), tl = strlen(to), o = 0;
    for (const char *p = s; *p && o < sizeof out - 1;) {
        if (fl && strncmp(p, from, fl) == 0) {
            if (o + tl >= sizeof out - 1) break;
            memcpy(out + o, to, tl); o += tl; p += fl;
        } else out[o++] = *p++;
    }
    out[o] = 0;
    snprintf(s, size, "%s", out);
}

/* Same as process_string() in MetricsFeeder/src/pipelines/json_to_TSDB_json.py, applied to tags host and command */
static int in_class(unsigned char c) {  /* [A-Za-z0-9_,:\\/\s] */
    return isalnum(c) || c == '_' || c == ',' || c == ':' || c == '\\' || c == '/' || isspace(c);
}

static void process_string(const char *in, char *out, size_t size) {
    char s[4096];
    size_t o = 0;
    for (const char *p = in; *p && o < sizeof s - 1; p++)
        if (*p != '(' && *p != ')') s[o++] = *p;
    s[o] = 0;
    /* First match of the character class; without a match the original string is kept unchanged */
    const char *start = s;
    while (*start && !in_class((unsigned char)*start)) start++;
    if (!*start) { snprintf(out, size, "%s", in); return; }
    const char *end = start;
    while (*end && in_class((unsigned char)*end)) end++;
    char matched[4096];
    snprintf(matched, sizeof matched, "%.*s", (int)(end - start), start);
    int words = 0, inword = 0;
    for (const char *p = matched; *p; p++) {
        int w = isalnum((unsigned char)*p) || *p == '_';
        if (w && !inword) words++;
        inword = w;
    }
    if (words > 1) {
        char repl[4096];
        snprintf(repl, sizeof repl, "%s", matched);
        replace_all(repl, sizeof repl, ",", "_comma_");
        replace_all(repl, sizeof repl, ":", "_twodot_");
        replace_all(repl, sizeof repl, "/", "_slash_");
        replace_all(repl, sizeof repl, " ", "_space_");
        replace_all(s, sizeof s, matched, repl);
    }
    snprintf(out, size, "%s", s);
}

/* ------------------------------------------------------------------------------------------------ output */
static sbuf batch;
static int batch_docs = 0;
static int sock = -1;
static void flush_batch(void);

static void add_doc(const char *metric, long ts, const char *value, const char *tags) {
    if (to_stdout) {
        printf("{\"metric\": \"%s\", \"timestamp\": \"%ld\", \"value\": \"%s\", \"tags\": {%s}}\n", metric, ts, value, tags);
        return;
    }
    char doc[1400];
    int len = snprintf(doc, sizeof doc, "{\"metric\": \"%s\", \"timestamp\": %ld, \"value\": %s, \"tags\": {%s}}", metric, ts, value, tags);
    if (len < 0 || len >= (int)sizeof doc) { log_err("document too long, discarded: %s", metric); return; }
    /* Body = "[" + docs separated by ", " + "]" */
    if (batch_docs > 0 && batch.len + 2 + len + 1 > MAX_BODY_BYTES) flush_batch();
    sb_add(&batch, "%s%s", batch_docs ? ", " : "[", doc);
    batch_docs++;
}

static int tsdb_connect(void) {
    struct addrinfo hints = {0}, *res;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(tsdb_host, tsdb_port, &hints, &res) != 0) { log_err("cannot resolve %s:%s", tsdb_host, tsdb_port); return -1; }
    int fd = -1;
    for (struct addrinfo *r = res; r; r = r->ai_next) {
        fd = socket(r->ai_family, r->ai_socktype, r->ai_protocol);
        if (fd < 0) continue;
        struct timeval tv = {3, 0};  /* POST_SEND_DOCS_TIMEOUT */
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
        if (connect(fd, r->ai_addr, r->ai_addrlen) == 0) break;
        close(fd); fd = -1;
    }
    freeaddrinfo(res);
    return fd;
}

/* Send the body with keep-alive; returns the HTTP status or -1 */
static int http_post(const char *body, size_t len) {
    char header[512];
    int hl = snprintf(header, sizeof header,
                      "POST /api/put HTTP/1.1\r\nHost: %s:%s\r\nContent-Type: application/json\r\n"
                      "Content-Length: %zu\r\nConnection: keep-alive\r\n\r\n", tsdb_host, tsdb_port, len);
    if (sock < 0 && (sock = tsdb_connect()) < 0) return -1;
    if (send(sock, header, hl, MSG_NOSIGNAL) != hl) goto fail;
    for (size_t sent = 0; sent < len;) {
        ssize_t n = send(sock, body + sent, len - sent, MSG_NOSIGNAL);
        if (n <= 0) goto fail;
        sent += n;
    }
    /* Read status line and headers, then discard the body */
    char resp[8192];
    size_t got = 0;
    char *hdr_end = NULL;
    while (!hdr_end) {
        ssize_t n = recv(sock, resp + got, sizeof resp - 1 - got, 0);
        if (n <= 0) goto fail;
        got += n; resp[got] = 0;
        hdr_end = strstr(resp, "\r\n\r\n");
        if (!hdr_end && got >= sizeof resp - 1) goto fail;
    }
    int status = 0;
    sscanf(resp, "HTTP/%*s %d", &status);
    long clen = 0;
    char *cl = strcasestr(resp, "Content-Length:");
    if (cl && cl < hdr_end) clen = atol(cl + 15);
    long body_got = (long)(got - (hdr_end + 4 - resp));
    while (body_got < clen) {
        ssize_t n = recv(sock, resp, sizeof resp, 0);
        if (n <= 0) goto fail;
        body_got += n;
    }
    char *conn = strcasestr(resp, "Connection: close");
    if (conn && conn < hdr_end) { close(sock); sock = -1; }
    return status;
fail:
    if (sock >= 0) close(sock);
    sock = -1;
    return -1;
}

static void flush_batch(void) {
    if (to_stdout || batch_docs == 0) return;
    sb_add(&batch, "]");
    int status = -1;
    for (int attempt = 0; attempt < 2 && status < 0; attempt++)
        status = http_post(batch.s, batch.len);
    /* As send_to_OpenTSDB.py: 204 ok */
    if (status != 204)
        log_err("couldn't post %d documents to %s:%s (status %d)", batch_docs, tsdb_host, tsdb_port, status);
    batch.len = 0;
    batch_docs = 0;
}

/* ------------------------------------------------------------------------------------------------ system */
typedef struct { u64 user, nice, sys, idle, wait; int valid; } cpu_counters;
static cpu_counters cpu_prev_total, cpu_prev[MAX_CPUS];

static void sample_cpu(long ts, int iv) {
    FILE *f = fopen("/proc/stat", "r");
    if (!f) return;
    char line[1024];
    cpu_counters total = {0}, cores[MAX_CPUS];
    int ncpu = 0, maxcore = -1;
    memset(cores, 0, sizeof cores);
    while (fgets(line, sizeof line, f)) {
        if (strncmp(line, "cpu", 3) != 0) break;
        cpu_counters c = {0};
        int core = -1;
        if (line[3] == ' ') {
            sscanf(line + 3, "%llu %llu %llu %llu %llu", &c.user, &c.nice, &c.sys, &c.idle, &c.wait);
        } else {
            sscanf(line + 3, "%d %llu %llu %llu %llu %llu", &core, &c.user, &c.nice, &c.sys, &c.idle, &c.wait);
        }
        c.valid = 1;
        if (core < 0) total = c;
        else if (core < MAX_CPUS) { cores[core] = c; ncpu++; if (core > maxcore) maxcore = core; }
    }
    fclose(f);

    char tags[600], value[64];
    snprintf(tags, sizeof tags, "\"host\": \"%s\"", host_tag);
    if (iv > 0 && g_CPU && cpu_prev_total.valid && ncpu > 0) {
        /* field_translator.py: usage = 100 * (system + user + nice + wait) / (ncpu * hertz * interval) */
        u64 busy = (total.sys - cpu_prev_total.sys) + (total.user - cpu_prev_total.user) +
                   (total.nice - cpu_prev_total.nice) + (total.wait - cpu_prev_total.wait);
        snprintf(value, sizeof value, "%.2f", 100.0 * busy / ((double)ncpu * hertz * iv));
        add_doc("sys.cpu.usage", ts, value, tags);
    }
    for (int i = 0; iv > 0 && g_cpu && i <= maxcore; i++) {
        if (!cores[i].valid || !cpu_prev[i].valid) continue;
        double tt = (double)iv * hertz;
        double kernel = (cores[i].sys - cpu_prev[i].sys) * 100.0 / tt;
        double user = (cores[i].user - cpu_prev[i].user) * 100.0 / tt;
        double nice = (cores[i].nice - cpu_prev[i].nice) * 100.0 / tt;
        double idle = (cores[i].idle - cpu_prev[i].idle) * 100.0 / tt;
        double wait = (cores[i].wait - cpu_prev[i].wait) * 100.0 / tt;
        snprintf(tags, sizeof tags, "\"host\": \"%s\", \"core\": \"%d\"", host_tag, i);
        snprintf(value, sizeof value, "%.2f", kernel); add_doc("sys.cpu.kernel", ts, value, tags);
        snprintf(value, sizeof value, "%.2f", user + nice); add_doc("sys.cpu.user", ts, value, tags);
        snprintf(value, sizeof value, "%.2f", idle); add_doc("sys.cpu.idle", ts, value, tags);
        snprintf(value, sizeof value, "%.2f", wait); add_doc("sys.cpu.wait", ts, value, tags);
    }
    cpu_prev_total = total;
    memcpy(cpu_prev, cores, sizeof cores);
}

static void sample_mem(long ts, int iv) {
    if (iv <= 0 || !(g_MEM || g_SWP)) return;
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return;
    char line[256], key[64];
    u64 v, memtotal = 0, memfree = 0, swapfree = 0;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%63s %llu", key, &v) != 2) continue;
        if (!strcmp(key, "MemTotal:")) memtotal = v;
        else if (!strcmp(key, "MemFree:")) memfree = v;
        else if (!strcmp(key, "SwapFree:")) swapfree = v;
    }
    fclose(f);
    char tags[600], total_s[64], free_s[64], value[64];
    snprintf(tags, sizeof tags, "\"host\": \"%s\"", host_tag);
    /* atop reports pages (KB * 1024 / pagesize); field_translator.py converts them to MB */
    u64 phys_pages = memtotal * 1024 / pagesize, free_pages = memfree * 1024 / pagesize;
    if (g_MEM && phys_pages > 0) {
        snprintf(total_s, sizeof total_s, "%.2f", (double)pagesize * phys_pages / 1048576.0);
        snprintf(free_s, sizeof free_s, "%.2f", (double)pagesize * free_pages / 1048576.0);
        add_doc("sys.mem.free", ts, free_s, tags);
        snprintf(value, sizeof value, "%.2f", 100.0 * (1 - atof(free_s) / atof(total_s)));
        add_doc("sys.mem.usage", ts, value, tags);
    }
    if (g_SWP) {
        u64 swap_pages = swapfree * 1024 / pagesize;
        snprintf(value, sizeof value, "%.2f", (double)pagesize * swap_pages / 1048576.0);
        add_doc("sys.swap.free", ts, value, tags);
    }
}

typedef struct { char name[64]; u64 rx, tx; } if_counters;
static if_counters if_prev[MAX_IFS];
static int n_if_prev = -1;

static long read_long_file(const char *path, long dflt) {
    FILE *f = fopen(path, "r");
    if (!f) return dflt;
    long v;
    int ok = fscanf(f, "%ld", &v) == 1;
    fclose(f);
    return ok ? v : dflt;
}

static int read_duplex(const char *ifname) {
    char path[256], buf[32] = "";
    snprintf(path, sizeof path, "/sys/class/net/%s/duplex", ifname);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    if (!fgets(buf, sizeof buf, f)) buf[0] = 0;
    fclose(f);
    return strncmp(buf, "full", 4) == 0;
}

static void sample_net(long ts, int iv) {
    FILE *f = fopen("/proc/net/dev", "r");
    if (!f) return;
    char line[512];
    if_counters cur[MAX_IFS];
    int n = 0;
    while (fgets(line, sizeof line, f) && n < MAX_IFS) {
        char *colon = strchr(line, ':');
        if (!colon) continue;
        *colon = 0;
        char *name = line;
        while (*name == ' ') name++;
        u64 rx, tx, d;
        if (sscanf(colon + 1, "%llu %llu %llu %llu %llu %llu %llu %llu %llu", &rx, &d, &d, &d, &d, &d, &d, &d, &tx) != 9) continue;
        snprintf(cur[n].name, sizeof cur[n].name, "%s", name);
        cur[n].rx = rx; cur[n].tx = tx;
        n++;
    }
    fclose(f);

    if (iv > 0 && g_NET && n_if_prev >= 0) {
        char tags[600], in_s[64], out_s[64], value[64];
        /* "upper" line of atop: field_filter.py creates the 'transport' and 'network' devices with constant
           values, so they are always sent as 0.00 */
        const char *upper[] = {"transport", "network"};
        for (int u = 0; u < 2; u++) {
            snprintf(tags, sizeof tags, "\"host\": \"%s\", \"device\": \"%s\"", host_tag, upper[u]);
            snprintf(in_s, sizeof in_s, "%.2f", 8.0 / (iv * 1048576.0));
            add_doc("sys.net.in.mb", ts, in_s, tags);
            add_doc("sys.net.out.mb", ts, in_s, tags);
            snprintf(value, sizeof value, "%.2f", 100.0 * (atof(in_s) + atof(in_s)) / 2.0);
            add_doc("sys.net.usage", ts, value, tags);
        }
        for (int i = 0; i < n; i++) {
            int p;
            for (p = 0; p < n_if_prev && strcmp(if_prev[p].name, cur[i].name); p++);
            if (p == n_if_prev) continue;
            char path[256];
            snprintf(path, sizeof path, "/sys/class/net/%s/speed", cur[i].name);
            long speed = read_long_file(path, 0);  /* Mbit/s, unknown -> 0 as atop */
            if (speed < 0) speed = 0;
            int duplex = read_duplex(cur[i].name);
            snprintf(tags, sizeof tags, "\"host\": \"%s\", \"device\": \"%s\"", host_tag, cur[i].name);
            snprintf(in_s, sizeof in_s, "%.2f", ((cur[i].rx - if_prev[p].rx) * 8) / (iv * 1048576.0));
            snprintf(out_s, sizeof out_s, "%.2f", ((cur[i].tx - if_prev[p].tx) * 8) / (iv * 1048576.0));
            add_doc("sys.net.in.mb", ts, in_s, tags);
            add_doc("sys.net.out.mb", ts, out_s, tags);
            if (speed > 0)
                snprintf(value, sizeof value, "%.2f", 100.0 * (atof(in_s) + atof(out_s)) / (duplex ? 2.0 * speed : (double)speed));
            else
                snprintf(value, sizeof value, "%ld", speed);  /* field_translator.py leaves the speed field */
            add_doc("sys.net.usage", ts, value, tags);
        }
    }
    memcpy(if_prev, cur, sizeof(if_counters) * n);
    n_if_prev = n;
}

/* ------------------------------------------------------------------------------------------------ processes */
typedef struct {
    int pid;
    u64 start, utime, stime, rsz, wsz;  /* rsz/wsz in 512-byte sectors, as atop */
    u64 vmem_kb, rmem_kb;
    char comm[64], state;
    int io_ok;
} proc_info;

static proc_info *prev_procs = NULL, *cur_procs = NULL;
static size_t n_prev = 0, n_cur = 0, cap_prev = 0, cap_cur = 0;

static int cmp_pid(const void *a, const void *b) { return ((const proc_info *)a)->pid - ((const proc_info *)b)->pid; }

static int read_proc(int pid, proc_info *p) {
    char path[64], buf[2048];
    snprintf(path, sizeof path, "/proc/%d/stat", pid);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    size_t n = fread(buf, 1, sizeof buf - 1, f);
    fclose(f);
    buf[n] = 0;
    char *lp = strchr(buf, '('), *rp = strrchr(buf, ')');
    if (!lp || !rp || rp < lp) return 0;
    /* atop keeps at most PNAMLEN (15) characters of the command name */
    int comm_len = (int)(rp - lp - 1);
    snprintf(p->comm, sizeof p->comm, "%.*s", comm_len < 15 ? comm_len : 15, lp + 1);
    u64 utime, stime, start, vsize;
    long long rss;
    /* Fields after the command: state(3) ... utime(14) stime(15) ... starttime(22) vsize(23) rss(24) */
    if (sscanf(rp + 2, "%c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %llu %llu %*d %*d %*d %*d %*d %*d %llu %llu %lld",
               &p->state, &utime, &stime, &start, &vsize, &rss) != 6) return 0;
    p->pid = pid;
    p->utime = utime; p->stime = stime; p->start = start;
    p->vmem_kb = vsize / 1024;                                   /* photoproc.c: vmem /= 1024 */
    p->rmem_kb = (u64)(rss > 0 ? rss : 0) * (pagesize / 1024);  /* photoproc.c: rmem *= pagesize/1024 */
    p->rsz = p->wsz = 0;
    p->io_ok = 0;
    if (g_PRD) {
        snprintf(path, sizeof path, "/proc/%d/io", pid);
        f = fopen(path, "r");
        if (f) {
            char line[128];
            u64 v;
            while (fgets(line, sizeof line, f)) {
                if (sscanf(line, "read_bytes: %llu", &v) == 1) p->rsz = v / 512;
                else if (sscanf(line, "write_bytes: %llu", &v) == 1) p->wsz = v / 512;
            }
            fclose(f);
            p->io_ok = 1;
        }
    }
    return 1;
}

static const proc_info *find_prev(int pid) {
    proc_info key;
    key.pid = pid;
    return bsearch(&key, prev_procs, n_prev, sizeof(proc_info), cmp_pid);
}

/* custom_filter.py: substring match on "(command)" */
static int command_excluded(const char *cmd, const char *const *list) {
    for (; *list; list++)
        if (strstr(cmd, *list)) return 1;
    return 0;
}

static void sample_procs(long ts, int iv) {
    n_cur = 0;
    DIR *d = opendir("/proc");
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!isdigit((unsigned char)e->d_name[0])) continue;
        if (n_cur == cap_cur) {
            cap_cur = cap_cur ? cap_cur * 2 : 256;
            cur_procs = realloc(cur_procs, cap_cur * sizeof(proc_info));
        }
        if (read_proc(atoi(e->d_name), &cur_procs[n_cur])) n_cur++;
    }
    closedir(d);
    qsort(cur_procs, n_cur, sizeof(proc_info), cmp_pid);

    static const char *const prc_prm_excluded[] = {"(kworker)", "(systemd)", "(migration)", "(rcu)", "(ksoftirq)", "(bioset)", NULL};
    static const char *const prd_excluded[] = {"(nethogs), (python), (kworker)", "(migration)", "(rcu)", "(ksoftirq)",
                                               "(bash)", "(bioset)", "(sshd)", "(ssh)", NULL};
    for (size_t i = 0; iv > 0 && i < n_cur; i++) {
        const proc_info *p = &cur_procs[i];
        /* validator.py: spaces break the number of fields; '@', '[' and ']' are not allowed */
        if (strpbrk(p->comm, " @[]\"\\") || strpbrk(host_tag, "@[]")) continue;
        char cmd[80], command_tag[256], tags[900], v1[64], v2[64];
        snprintf(cmd, sizeof cmd, "(%s)", p->comm);
        process_string(cmd, command_tag, sizeof command_tag);
        snprintf(tags, sizeof tags, "\"host\": \"%s\", \"pid\": \"%d\", \"command\": \"%s\"", host_tag, p->pid, command_tag);

        /* Counters of a new process (or a reused pid) are taken since its start, as atop does */
        const proc_info *q = find_prev(p->pid);
        if (q && q->start != p->start) q = NULL;
        int excluded = command_excluded(cmd, prc_prm_excluded);

        if (g_PRC && !excluded) {
            u64 du = p->utime - (q ? q->utime : 0), ds = p->stime - (q ? q->stime : 0);
            snprintf(v1, sizeof v1, "%.2f", 1.0 * du / iv);
            snprintf(v2, sizeof v2, "%.2f", 1.0 * ds / iv);
            /* value_filter.py: user + kernel + sleep average (always 0 in current kernels) < 0.05 */
            if (atof(v1) + atof(v2) + 0.0 >= 0.05) {
                add_doc("proc.cpu.user", ts, v1, tags);
                add_doc("proc.cpu.kernel", ts, v2, tags);
            }
        }
        /* custom_filter.py looks for the command in column 5, which is the state in PRM lines: no PRM line is
           ever excluded by command */
        if (g_PRM) {
            snprintf(v1, sizeof v1, "%.2f", p->vmem_kb / 1024.0);
            snprintf(v2, sizeof v2, "%.2f", p->rmem_kb / 1024.0);
            if (atof(v1) >= 10.0 && atof(v2) >= 10.0) {
                add_doc("proc.mem.virtual", ts, v1, tags);
                add_doc("proc.mem.resident", ts, v2, tags);
            }
        }
        if (g_PRD && !command_excluded(cmd, prd_excluded)) {
            u64 dr = p->rsz - (q && q->io_ok ? q->rsz : 0), dw = p->wsz - (q && q->io_ok ? q->wsz : 0);
            if (!p->io_ok) dr = dw = 0;
            snprintf(v1, sizeof v1, "%.2f", dr * 512.0 / (iv * 1048576.0));
            snprintf(v2, sizeof v2, "%.2f", dw * 512.0 / (iv * 1048576.0));
            /* value_filter.py keeps (systemd) lines whatever their values */
            if (!strcmp(cmd, "(systemd)") || atof(v1) + atof(v2) >= 0.05) {
                add_doc("proc.disk.reads.mb", ts, v1, tags);
                add_doc("proc.disk.writes.mb", ts, v2, tags);
            }
        }
    }
    /* Current sample becomes the previous one (buffers are swapped and reused) */
    proc_info *tmp = prev_procs;
    size_t tmp_cap = cap_prev;
    prev_procs = cur_procs; cap_prev = cap_cur; n_prev = n_cur;
    cur_procs = tmp; cap_cur = tmp_cap;
}

/* ------------------------------------------------------------------------------------------------ config */
static void read_services_config(void) {
    const char *bdw = getenv("BDWATCHDOG_PATH");
    char path[1024];
    snprintf(path, sizeof path, "%s/services_config.yml", bdw ? bdw : "/opt/BDWatchdog");
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[512], key[128], val[256];
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, " %127[^:]: %255s", key, val) != 2) continue;
        char *v = val;
        size_t l = strlen(v);
        if (l >= 2 && (v[0] == '"' || v[0] == '\'')) { v[l - 1] = 0; v++; }
        if (!strcmp(key, "OPENTSDB_URL") && !tsdb_host[0]) snprintf(tsdb_host, sizeof tsdb_host, "%s", v);
        if (!strcmp(key, "OPENTSDB_PORT") && !tsdb_port[0]) snprintf(tsdb_port, sizeof tsdb_port, "%s", v);
    }
    fclose(f);
}

static void parse_groups(const char *list) {
    g_CPU = g_cpu = g_MEM = g_SWP = g_NET = g_PRC = g_PRM = g_PRD = 0;
    char buf[256];
    snprintf(buf, sizeof buf, "%s", list);
    for (char *t = strtok(buf, ","); t; t = strtok(NULL, ",")) {
        if (!strcmp(t, "CPU")) g_CPU = 1;
        else if (!strcmp(t, "cpu")) g_cpu = 1;
        else if (!strcmp(t, "MEM")) g_MEM = 1;
        else if (!strcmp(t, "SWP")) g_SWP = 1;
        else if (!strcmp(t, "NET")) g_NET = 1;
        else if (!strcmp(t, "PRC")) g_PRC = 1;
        else if (!strcmp(t, "PRM")) g_PRM = 1;
        else if (!strcmp(t, "PRD")) g_PRD = 1;
        else log_err("unknown group '%s' ignored", t);
    }
}

static void sleep_until(double t) {
    struct timespec ts = {(time_t)t, (long)((t - (time_t)t) * 1e9)};
    while (clock_nanosleep(CLOCK_REALTIME, TIMER_ABSTIME, &ts, NULL) == EINTR);
}

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

int main(int argc, char **argv) {
    int opt;
    while ((opt = getopt(argc, argv, "i:H:P:g:sc:")) != -1) {
        switch (opt) {
            case 'i': interval = atoi(optarg); break;
            case 'H': snprintf(tsdb_host, sizeof tsdb_host, "%s", optarg); break;
            case 'P': snprintf(tsdb_port, sizeof tsdb_port, "%s", optarg); break;
            case 'g': parse_groups(optarg); break;
            case 's': to_stdout = 1; break;
            case 'c': max_samples = atol(optarg); break;
            default:
                fprintf(stderr, "Usage: %s [-i interval] [-H opentsdb_host] [-P opentsdb_port] [-g groups] [-s] [-c count]\n", argv[0]);
                return 1;
        }
    }
    if (interval < 1) interval = 1;
    hertz = sysconf(_SC_CLK_TCK);
    pagesize = sysconf(_SC_PAGESIZE);
    if (!to_stdout) {
        read_services_config();
        if (!tsdb_host[0]) snprintf(tsdb_host, sizeof tsdb_host, "opentsdb");
        if (!tsdb_port[0]) snprintf(tsdb_port, sizeof tsdb_port, "4242");
    }
    char hostname[256] = "";
    gethostname(hostname, sizeof hostname - 1);
    process_string(hostname, host_tag, sizeof host_tag);
    setvbuf(stdout, NULL, _IOLBF, 0);

    /* First sample is only a reference (atop's first sample since boot is discarded by atop_to_json.py) */
    double t_prev = now_s();
    sample_cpu(0, 0); sample_mem(0, 0); sample_net(0, 0); sample_procs(0, 0);
    for (long k = 0; max_samples < 0 || k < max_samples; k++) {
        double next = ((long)(now_s() / interval) + 1) * (double)interval;
        sleep_until(next);
        double t = now_s();
        long ts = (long)(t + 0.5);
        int iv = (int)(t - t_prev + 0.5);
        if (iv < 1) iv = 1;
        t_prev = t;
        if (g_CPU || g_cpu) sample_cpu(ts, iv);
        sample_mem(ts, iv);
        sample_net(ts, iv);
        if (g_PRC || g_PRM || g_PRD) sample_procs(ts, iv);
        flush_batch();
    }
    return 0;
}
