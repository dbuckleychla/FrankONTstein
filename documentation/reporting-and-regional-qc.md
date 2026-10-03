# Sample reports and regional read-length QC

Open the run `index.html`, then the sample summary. Summaries contain analysis
status, review warnings, separate classifier results, NASVAR copy-number and
karyotype estimates, and caller-attributed fusion/variant evidence, followed by QC.
Fusion summaries appear before the NASVAR plots and show `GENE1::GENE2`, native coordinates, and the caller-reported
total supporting reads per event; breakpoint counts and different callers are
never summed. Missing native fields display Unavailable.
QC retains one primary-genome 5mCpG beta histogram; 5mC/5hmC metrics remain
separate in tables and machine-readable outputs. GC-versus-coverage plots are
omitted from the summary, while native NASVAR artifacts remain available. Original
NASVAR reports and JSON remain available; the summary does not reinterpret calls.
All charts are embedded for offline use. Copy the complete published sample tree
to retain links to original artifacts.

## Regional read lengths

QC schema version 2 adds `alignment.read_lengths.on_target` and `off_target`.
Existing fields retain their meanings. Each primary mapped alignment belongs to
one target group and one enrichment group, based on any aligned-block overlap
with the corresponding merged BED intervals. Deletions and reference skips do
not confer overlap. These are overlapping comparisons, not three exclusive bins.
Unmapped reads are reported separately. Secondary/supplementary records are
excluded; duplicate and QC-failed primary records remain included. Read length
is the sequenced query length, including soft clipping, not the reference span.
Read-length summaries include all BAM contigs; aggregate coverage and CpG metrics
retain their primary-chromosome denominators.

Mean, median and N50 use exact length frequencies. N50 is the length where the
longest reads account for at least half the sequenced bases. Histograms compact
the existing 100-bp display bins into logarithmic bins (12 per decade); bin 0 is
placed at 1 bp on the log axis. This affects visualization only, not statistics.
Target and enrichment histograms appear side by side on wide screens and stack
on narrow screens. Each histogram uses the number of reads in its own group as
its denominator.
No per-read database or full per-base intermediate table is produced.

Counts use separators; displayed lengths use whole bp, mean depths one decimal,
and percentages one decimal. Tiny positive percentages display `<0.1%`.
JSON/TSV retain precision; undefined values remain null and display Unavailable.
Legacy reports without target-specific length metrics show Unavailable.

## Preview existing outputs

`bin/read_length_qc.py` performs a focused streaming BAM pass without recomputing
coverage, methylation, or callers. Supply the exact target/enrichment BEDs; its
output records their paths and SHA-256 hashes. Do not substitute a similarly
named BED. Confirm the target coordinates against the original target QC table
and recorded provenance.

```bash
python bin/read_length_qc.py --bam sample.bam --targets targets.bed \
  --enrichment enrichment.bed --output sample.read_lengths.json
python bin/preview_reports.py original-run preview-run \
  --lengths sample.read_lengths.json
```

The preview tool preserves originals, checks existing length groups against the
audit, and copies only small report artifacts. Use one original singleton run per
length audit. Omitting `--lengths` renders legacy QC without inventing statistics.
Quarto is the default renderer; `--renderer /path/to/pandoc` is an explicit preview
fallback and does not validate the production Quarto process. Previews are marked
as previews and record their source and renderer in the manifest.

## Resume and validation

Use a fresh output directory for the redesigned layout: publication does not
remove old files. Changed QC and summary tasks must regenerate; unchanged
basecalling/alignment/caller tasks remain eligible for cache reuse with the same
work directory and explicit resume session.

Run `test_qc.py`, `test_report_presentation.py`, `test_sample_summary.py`, publication
checks, Nextflow 26 strict-syntax plan checks, and routing/resume contracts. Inspect
real-data previews for axes, warnings, empty results, offline images, and artifact
links. Stub routing does not validate scientific measurements or classifiers.
