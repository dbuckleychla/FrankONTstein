# Methylation and adaptive-sampling QC

All tiers now run modkit CpG pileup and comprehensive sample QC. Disable only the
new QC calculations with `--disable-qc true` (or `disable_qc: true` in YAML).
The CLI hyphenated alias takes precedence over the YAML setting. CpG bedMethyl, Classy, BAM checks,
and reference validation remain enabled.

## Outputs

- `<sample>/methylation/<sample>.cpg.bedmethyl.gz` and `.tbi`: BGZF-compressed,
  indexed modkit CpG dyads with complementary strands combined and separate
  `m` (5mC) and `h` (5hmC) records when present.
- `<sample>/methylation/<sample>.modkit.log`: modkit probability-threshold
  estimation and execution log. The default thresholds belong to the locked
  modkit version; they are not a fixed workflow-wide probability cutoff.
- `<sample>/methylation/classy/`: existing classifier outputs.
- `<sample>/qc/index.html`: self-contained report with SVG plots, no CDN.
- `<sample>/qc/metrics.json`: versioned metrics, definitions and plot histograms.
- `<sample>/qc/summary.tsv`: scalar summaries.
- `<sample>/qc/targets.tsv`: original target labels (prefixed by BED line number),
  interval coverage and breadth at both mapping-quality thresholds.
- Root `index.html`: cross-sample QC table and report links. Root `manifest.json`
  records bedMethyl and QC statuses independently of Classy.

## Definitions

Input read/base totals reuse preprocessing checks. Multiplexed input totals are
labelled by **run**, rather than attributed to each sample. When demultiplexing,
QC also counts reads and bases per barcode and for unclassified output; this
requires an additional streamed read through those BAMs. Trimming QC records
post-trim counts. The aligned BAM provides sample-level primary read yield.

Alignment rate uses mapped primary reads / all primary reads, including unmapped
reads in the denominator. Secondary/supplementary alignments are counted
separately. Length summaries use query sequence length, including soft clips,
with exact mean, median and N50; hard-clipped sequence cannot be recovered.

A primary read is on-enrichment when at least one aligned query base overlaps the
merged enrichment BED. Deletions and reference skips do not establish overlap.
Both mapped-read and all-primary-read denominators are reported. Lengths and
mapping-quality histograms include all primary reads regardless of duplicate or
QC-failed flags.

Coverage is computed separately at MAPQ ≥0 and ≥20 with base quality ≥0, including
duplicate/QC-failed primary records, excluding secondary/supplementary records,
deletions and skipped reference positions. Aggregate genome, enrichment, target,
and off-enrichment coverage uses chromosomes 1–22/X/Y (UCSC, bare chromosome or
RefSeq naming). Other contigs remain in the per-contig metrics and per-target TSV.
Overlapping BED intervals are merged for aggregate denominators; original target
intervals retain independent summaries. Mean depth and breadth include uncovered
bases. N bases in the reference remain in these coordinate-based denominators.

Mean on-enrichment depth / mean off-enrichment depth is **observed enrichment**,
not an adaptive-sampling acceptance or rejection rate. The latter cannot be
reconstructed from a basecalled BAM alone. A zero denominator produces null.

CpG metrics count dyads by the forward-strand C coordinate. Beta uses valid calls,
not all alignments: combined modified-C beta includes 5mC and 5hmC, with separate
fractions for each modification. Coverage is counted once per dyad, even when
both modification records occur. Missing modification types are unavailable,
not zero. Reports include site-average and depth-weighted beta, all-site and
≥10-call beta distributions, valid-depth histograms and counts at ≥1/5/10/20.
Reference CpG denominators are counted from the supplied FASTA. No differential
methylation analysis or clinical pass/fail thresholds are applied.

## Large BAMs and execution

Modkit uses the allocated thread count (default 8). SAMPLE_QC also defaults to 8
CPUs: BAM/depth work uses at most four concurrent contigs (one Python worker and
one samtools subprocess per slot), then indexed CpG summaries and reference
scanning run with up to eight contig workers. All limits respect `--max_cpus`.
These defaults favor bounded memory over loading reads or per-base tables.

Each contig has one read-statistics pass and two streamed samtools depth passes.
No depth file or per-read database is written. Exact length-frequency counts and
aggregated depth histograms are retained; plot length bins are 100 bp. CpG FASTA
scanning uses 1 Mb chunks, and bedMethyl is read through its tabix index.
Parallelism is limited by the number of contigs and storage throughput: network
storage can saturate before CPUs do. Reducing the SAMPLE_QC CPU allocation also
reduces concurrent readers.

Classy still performs its own internal pileup, preserving existing classifier
behavior. The separate modkit export is therefore additional work. Reusing a
shared pileup for classification requires independent compatibility validation.

`MODKIT_PILEUP` reuses the locked Classy image; the other new tasks reuse the
preprocessing image. No new image key or reference asset is required. The locked
modkit must support `--cpg --modified-bases m h --combine-strands --bgzf --log-filepath`. Actual modkit
and container execution must be verified on a supported Linux host; stub runs
exercise wiring, not biological calculations.
