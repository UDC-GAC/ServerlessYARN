/*
 *  Copyright (c) 2018, INRIA
 *  Copyright (c) 2018, University of Lille
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *
 *  * Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 *
 *  * Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 *  * Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 *  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 *  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 *  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 *  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 *  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 *  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 *  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <regex.h>

#include "target.h"
#include "target_apptainer.h"

/*
 * CONTAINER_ID_REGEX is the regex used to extract the Apptainer container id from the cgroup path.
 * CONTAINER_ID_REGEX_EXPECTED_MATCHES is the number of expected matches from the regex. (num groups + 1)
 */
#define CONTAINER_ID_REGEX "perf_event/system.slice/apptainer-([0-9]+)\\.scope"
#define CONTAINER_ID_REGEX_EXPECTED_MATCHES 2

/*
 * CONTAINER_NAME_REGEX is the regex used to extract the Apptainer container name from its environment file.
 * CONTAINER_NAME_REGEX_EXPECTED_MATCHES is the number of expected matches from the regex. (num groups + 1)
 */
#define CONTAINER_NAME_REGEX "\"containerID\":\"([^\"]+)\""
#define CONTAINER_NAME_REGEX_EXPECTED_MATCHES 2

/*
 * ENV_FILE_RELEVANT_CHARACTERS is the number of characters to read from environment files of Apptainer containers.
 */
#define ENV_FILE_RELEVANT_CHARACTERS 512


static char *
build_container_config_path(const char *cgroup_path)
{
    regex_t re;
    regmatch_t matches[CONTAINER_ID_REGEX_EXPECTED_MATCHES];
    char *target_id = NULL;
    char buffer[PATH_MAX];
    char *config_path = NULL;

    if (!regcomp(&re, CONTAINER_ID_REGEX, REG_EXTENDED | REG_NEWLINE)) {
        if (!regexec(&re, cgroup_path, CONTAINER_ID_REGEX_EXPECTED_MATCHES, matches, 0)) {
            target_id = strndup(cgroup_path + matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so);
            if (target_id != NULL) {
                snprintf(buffer, PATH_MAX, "/host_proc/%s/environ", target_id);
                config_path = strdup(buffer);
                free(target_id);
            }
        }
        regfree(&re);
    }
    return config_path;
}


char *
target_apptainer_resolve_name(struct target *target)
{
    regex_t re;
    regmatch_t matches[CONTAINER_ID_REGEX_EXPECTED_MATCHES];
    FILE *env_file = NULL;
    char *env_data = NULL;
    char *target_name = NULL;
    char *config_path = NULL;
    size_t env_len;

    /* Get path from process environment file belonging to the container in host (e.g., /host_proc/<pid>/environ) */
    config_path = build_container_config_path(target->cgroup_path);
    if (!config_path)
        return NULL;

    /* Open container environment file */
    env_file = fopen(config_path, "r");
    free(config_path);
    if (!env_file)
        return NULL;

    /* Read container environment file */
    env_data = malloc(sizeof(char) * (ENV_FILE_RELEVANT_CHARACTERS + 1));
    env_len = fread(env_data, 1, ENV_FILE_RELEVANT_CHARACTERS, env_file);
    if (env_len > 0) {
        /* Replace null bytes '\0' with break lines '\n', as env file separates environment variables with '\0'*/
        env_data[env_len] = '\0';
        for (size_t i = 0; i < env_len; i++) {
            if (env_data[i] == '\0')
                env_data[i] = '\n';
        }
        /* Search container name in environment data */
        if (!regcomp(&re, CONTAINER_NAME_REGEX, REG_EXTENDED | REG_NEWLINE)) {
            if (!regexec(&re, env_data, CONTAINER_NAME_REGEX_EXPECTED_MATCHES, matches, 0)) {
                target_name = strndup(env_data + matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so);
            }
            regfree(&re);
        }
    }
    fclose(env_file);
    free(env_data);

    return target_name;
}
