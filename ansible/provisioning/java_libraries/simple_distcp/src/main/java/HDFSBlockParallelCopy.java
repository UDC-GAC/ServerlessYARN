// MapReduce job that copies data from HDFS src to dst with block-level parallelism
// and binary safety. Each map copies exactly one InputSplit (aligned with HDFS blocks)
// to a temporary chunk file. The job OutputCommitter assembles chunks into final files
// using FileSystem.concat (O(1) metadata concat), preserving binary identity.

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FSDataInputStream;
import org.apache.hadoop.fs.FSDataOutputStream;
import org.apache.hadoop.fs.FileStatus;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.LocatedFileStatus;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.fs.RemoteIterator;
import org.apache.hadoop.io.IOUtils;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.mapreduce.lib.input.FileSplit;
import org.apache.hadoop.mapreduce.InputSplit;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.JobContext;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.OutputCommitter;
import org.apache.hadoop.mapreduce.RecordReader;
import org.apache.hadoop.mapreduce.RecordWriter;
import org.apache.hadoop.mapreduce.TaskAttemptContext;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.OutputFormat;

import org.apache.hadoop.mapreduce.JobStatus.State;

import java.io.IOException;
import java.util.*;

public class HDFSBlockParallelCopy {

  /** InputFormat that yields exactly one (empty) record per split. We rely on
   * FileInputFormat's default split computation which aligns splits to HDFS blocks. */
  public static class BlockPerSplitInputFormat extends FileInputFormat<NullWritable, NullWritable> {
    @Override
    protected boolean isSplitable(JobContext context, Path file) {
      return true; // allow splits; defaults will align to block boundaries
    }

    @Override
    public RecordReader<NullWritable, NullWritable> createRecordReader(
        InputSplit split, TaskAttemptContext context) throws IOException, InterruptedException {
      return new RecordReader<NullWritable, NullWritable>() {
        private boolean emitted = false;
        @Override public void initialize(InputSplit split, TaskAttemptContext context) {}
        @Override public boolean nextKeyValue() { if (!emitted) { emitted = true; return true; } return false; }
        @Override public NullWritable getCurrentKey() { return NullWritable.get(); }
        @Override public NullWritable getCurrentValue() { return NullWritable.get(); }
        @Override public float getProgress() { return emitted ? 1.0f : 0.0f; }
        @Override public void close() {}
      };
    }
  }

  /** Mapper: copies only the (start,length) range of the split into a temp chunk file. */
  public static class BlockCopyMapper extends Mapper<NullWritable, NullWritable, NullWritable, NullWritable> {
    private Path srcRoot, dstRoot;
    private int buffer;
    private boolean overwrite;

    @Override
    protected void setup(Context ctx) {
      Configuration conf = ctx.getConfiguration();
      srcRoot   = new Path(conf.get("copy.src.root"));
      dstRoot   = new Path(conf.get("copy.dst.root"));
      buffer    = conf.getInt("copy.buffer.bytes", 1 * 1024 * 1024); // 1MB default
      overwrite = conf.getBoolean("copy.overwrite", false);
    }

    @Override
    protected void map(NullWritable k, NullWritable v, Context ctx) throws IOException, InterruptedException {
      FileSplit split = (FileSplit) ctx.getInputSplit();
      Path srcFile = split.getPath();
      long start = split.getStart();
      long len   = split.getLength();

      FileSystem srcFs = srcFile.getFileSystem(ctx.getConfiguration());
      FileStatus srcStat = srcFs.getFileStatus(srcFile);

      // Build destination directory and chunk path
      Path rel = new Path(makeRelative(srcRoot, srcFile));
      Path dstDir  = new Path(dstRoot, rel.getParent() == null ? new Path(".") : rel.getParent());
      String base  = rel.getName();
      String chunkName = String.format(".copying.%s.part-%012d", base, start);
      Path chunkPath = new Path(dstDir, chunkName);

      FileSystem dstFs = chunkPath.getFileSystem(ctx.getConfiguration());
      dstFs.mkdirs(dstDir);

      short repl     = (short) ctx.getConfiguration().getInt("copy.replication", srcStat.getReplication());
      long  blockSz  = ctx.getConfiguration().getLong("copy.blocksize",  srcStat.getBlockSize());

      try (FSDataInputStream in  = srcFs.open(srcFile, buffer);
           FSDataOutputStream out = dstFs.create(chunkPath, overwrite, buffer, repl, blockSz)) {
        in.seek(start);
        long toCopy = len;
        byte[] buf = new byte[buffer];
        while (toCopy > 0) {
          int r = in.read(buf, 0, (int)Math.min(buf.length, toCopy));
          if (r < 0) break;
          out.write(buf, 0, r);
          toCopy -= r;
        }
        out.hflush();
      }

      // Preserve permissions and times on the chunk (final file inherits from first chunk)
      FileStatus st = dstFs.getFileStatus(chunkPath);
      dstFs.setPermission(chunkPath, srcStat.getPermission());
      dstFs.setTimes(chunkPath, srcStat.getModificationTime(), srcStat.getAccessTime());
    }

    private static String makeRelative(Path root, Path p) {
      String b = root.toUri().getPath();
      String f = p.toUri().getPath();
      if (f.startsWith(b)) {
        String r = f.substring(b.length());
        return r.startsWith("/") ? r.substring(1) : r;
      }
      return p.getName();
    }
  }

  /** OutputFormat that does not write records; its committer assembles chunk files into final files. */
  public static class CopyOutputFormat extends OutputFormat<NullWritable, NullWritable> {

    @Override
    public RecordWriter<NullWritable, NullWritable> getRecordWriter(TaskAttemptContext ctx) {
      return new RecordWriter<NullWritable, NullWritable>() {
        @Override public void write(NullWritable k, NullWritable v) {}
        @Override public void close(TaskAttemptContext ctx) {}
      };
    }

    @Override
    public void checkOutputSpecs(JobContext context) throws IOException, InterruptedException {
      // No default output directory to check.
    }

    @Override
    public OutputCommitter getOutputCommitter(TaskAttemptContext ctx) throws IOException, InterruptedException {
      return new ConcatCommitter();
    }

    /**
     * OutputCommitter that:
     *  - groups temp chunks (.copying.<name>.part-<offset>) by final file
     *  - renames the first chunk to final name
     *  - concatenates the rest via FileSystem.concat(final, sources[])
     *  - cleans up on abort
     */
    static class ConcatCommitter extends OutputCommitter {
      @Override public void setupJob(JobContext jobContext) {}

      @Override
      public void commitJob(JobContext jobContext) throws IOException {
        Configuration conf = jobContext.getConfiguration();
        Path dstRoot = new Path(conf.get("copy.dst.root"));
        Path srcRoot = new Path(conf.get("copy.src.root"));

        FileSystem dstFs = dstRoot.getFileSystem(conf);

        // 1) Assemble all chunk files per final path
        Map<Path, List<Path>> chunksByFile = new HashMap<>();
        RemoteIterator<LocatedFileStatus> it = dstFs.listFiles(dstRoot, true);
        while (it.hasNext()) {
          LocatedFileStatus st = it.next();
          if (!st.isFile()) continue;
          String n = st.getPath().getName();
          if (!n.startsWith(".copying.") || !n.contains(".part-")) continue;

          String base = n.substring(".copying.".length(), n.lastIndexOf(".part-"));
          Path parent = st.getPath().getParent();
          Path finalPath = new Path(parent, base);
          chunksByFile.computeIfAbsent(finalPath, k -> new ArrayList<>()).add(st.getPath());
        }

        // 2) For each final file: rename first chunk and concat the rest
        for (Map.Entry<Path, List<Path>> e : chunksByFile.entrySet()) {
          Path finalPath = e.getKey();
          List<Path> parts = e.getValue();
          if (parts.isEmpty()) continue;

          parts.sort(Comparator.comparingLong(p -> {
            String n = p.getName();
            String off = n.substring(n.lastIndexOf(".part-") + 6);
            return Long.parseLong(off);
          }));

          // Ensure clean slate
          dstFs.delete(finalPath, false);

          if (parts.size() == 1) {
            dstFs.rename(parts.get(0), finalPath);
          } else {
            Path target = parts.get(0);
            // Move first part to final name then concat others
            dstFs.rename(target, finalPath);
            Path[] sources = parts.subList(1, parts.size()).toArray(new Path[0]);
            dstFs.concat(finalPath, sources);
          }
        }

        // 3) Create empty files (0 bytes) that have no chunks
        FileSystem srcFs = srcRoot.getFileSystem(conf);
        RemoteIterator<LocatedFileStatus> srcIter = srcFs.listFiles(srcRoot, true);
        while (srcIter.hasNext()) {
          LocatedFileStatus s = srcIter.next();
          if (!s.isFile()) continue;
          if (s.getLen() != 0L) continue;
          Path rel = makeRelativePath(srcRoot, s.getPath());
          Path dstEmpty = new Path(dstRoot, rel);
          if (!dstFs.exists(dstEmpty)) {
            dstFs.mkdirs(dstEmpty.getParent());
            // create empty file
            try (FSDataOutputStream out = dstFs.create(dstEmpty, true)) { out.hflush(); }
            dstFs.setPermission(dstEmpty, s.getPermission());
            dstFs.setTimes(dstEmpty, s.getModificationTime(), s.getAccessTime());
          }
        }
      }

      @Override
      public void abortJob(JobContext jobContext, State status) throws IOException {
        // Cleanup temporary chunk files
        Configuration conf = jobContext.getConfiguration();
        Path dstRoot = new Path(conf.get("copy.dst.root"));
        FileSystem fs = dstRoot.getFileSystem(conf);
        RemoteIterator<LocatedFileStatus> it = fs.listFiles(dstRoot, true);
        while (it.hasNext()) {
          Path p = it.next().getPath();
          String n = p.getName();
          if (n.startsWith(".copying.") && n.contains(".part-")) {
            fs.delete(p, false);
          }
        }
      }

      @Override public void setupTask(TaskAttemptContext taskContext) {}
      @Override public boolean needsTaskCommit(TaskAttemptContext taskContext) { return false; }
      @Override public void commitTask(TaskAttemptContext taskContext) {}
      @Override public void abortTask(TaskAttemptContext taskContext) {}

      private static Path makeRelativePath(Path root, Path p) {
        String b = root.toUri().getPath();
        String f = p.toUri().getPath();
        if (f.startsWith(b)) {
          String r = f.substring(b.length());
          if (r.startsWith("/")) r = r.substring(1);
          return new Path(r.isEmpty() ? p.getName() : r);
        }
        return new Path(p.getName());
      }
    }
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 2) {
      System.err.println("Usage: HDFSBlockParallelCopy <src_path> <dst_path>");
      System.exit(-1);
    }
    Configuration conf = new Configuration();
    Path src = new Path(args[0]);
    Path dst = new Path(args[1]);
    conf.set("copy.src.root", src.toString());
    conf.set("copy.dst.root", dst.toString());

    Job job = Job.getInstance(conf, "HDFS Block-Parallel Copy (binary-safe)");
    job.setJarByClass(HDFSBlockParallelCopy.class);

    // Splits: by default, FileInputFormat uses HDFS block size as upper bound.
    job.setInputFormatClass(BlockPerSplitInputFormat.class);
    FileInputFormat.addInputPath(job, src);
    FileInputFormat.setInputDirRecursive(job, true);

    // Mapper-only job, speculative disabled to avoid duplicate chunk writes
    job.setMapperClass(BlockCopyMapper.class);
    job.setNumReduceTasks(0);
    job.getConfiguration().setBoolean("mapreduce.map.speculative", false);

    // Custom OutputFormat that assembles chunks in commitJob
    job.setOutputFormatClass(CopyOutputFormat.class);

    System.exit(job.waitForCompletion(true) ? 0 : 1);
  }
}