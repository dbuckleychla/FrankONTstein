# Variant outputs and run-review mitigations

Each VCF/BCF-producing caller retains its original output. Existing small-variant
target-filtered files remain unchanged. A separate FINALIZE_VARIANTS task adds:

- `<sample>.<kind>.normalized.vcf.gz` and `.tbi`: all records, canonical sample identity.
- `<sample>.<kind>.pass.vcf.gz` and `.tbi`: exact `FILTER=PASS` records only.
- `<sample>.<kind>.filtering.json`: record/filter counts, input sample labels and applicability.

Small variants receive these outputs for raw and target-restricted call sets;
SV/CNV VCFs receive them for their existing unrestricted call sets. No new target
restriction is applied to SV/CNV callers. A VCF containing only unassessed `.`
FILTER values does not produce a misleading PASS subset; its JSON records that
PASS filtering is not applicable. Explicitly filtered all-fail inputs produce
valid empty indexed PASS VCFs. Empty filter-declaring VCFs do likewise. Dot is
never promoted to PASS. NASVAR/ichorCNA/SubChrom scientific results are JSON/tables,
not VCF FILTER-bearing call sets, and are not arbitrarily filtered. SubChrom's
copied Clair3 input VCF is already covered by Clair3's finalized outputs.

Sample SM values are normalized on aligned BAM headers while retaining RG IDs,
sequences and read-level MM/ML/MN/mv tags. Sniffles gets an explicit sample ID;
QDNAseq receives a sample-named input link. Final VCF copies consistently use the
sample ID, and QDNAseq bare chromosome names are resolved against the validated
FAI. Ambiguous multisample VCFs fail rather than silently choosing a sample.
Caller-native originals are retained for provenance, so downstream consumers
should use normalized/PASS deliverables when they need uniform headers.

Caller stdout/stderr now appear in per-process directories beneath each caller's
results. They are captured inside the task script and drained before exit, so
AWS Batch can stage them as declared outputs. An `afterScript` hook must not be
used to create required output files. Former direct oncoseq imports use local copies of the pinned definitions
with log outputs added; no vendor gitlink was changed. Classy keeps a runtime log. Publication runs the sidecar audit in the
Python-equipped preprocessing image and emits `artifact_audit.json/.txt` listing absent referenced sidecars without
removing embedded model results. NASVAR emits `quality_warnings.json/.txt` with
insufficient-MAF/blast-ratio and duplicate-locus warnings. The top-level report
links the Classy audit and displays sample QC depth/MAPQ warnings.

Reference preparation normalizes repeat contigs only through aliases explicitly
declared by the NASVAR reference configuration; unmatched repeats are excluded
from NASVAR's staged input and retained in
`pipeline_info/reference_audit/repeats.excluded.bed`. The accompanying JSON counts
exclusions and duplicate target names across chromosomes. Targets are unchanged:
no padding, deduplication of biological loci or guessing of Y/PAR mappings.
Discordant sex-chromosome/purity estimates remain separate and require review.
No reference masking, sex assignment or clinical threshold is inferred automatically.

BAM checks use quickcheck and at most 1,000 records for tag presence and header
sanity. They do not decode MM/ML or validate MN/move-table values. `idxstats`
replaces the redundant flagstat scan. Full QC still computes requested coverage
and methylation summaries unless disabled. Sampled input counts are explicitly
labeled, with unknown full-run yield represented as null.

Resources now follow the partial-run audit: alignment 32 CPUs/64 GB, demultiplexing
8 CPUs/8 GB, QC 16 CPUs/4 GB, Classy/modkit 8 CPUs/16 GB, DeepSomatic 8 CPUs/64 GB;
serial jobs are reduced. Global caps apply. The trace TSV includes resource and
timing fields. These are initial budgets needing a larger-run benchmark. In
particular, DeepSomatic subprocess memory accounting/internal worker counts and
GPU VRAM/utilization still need measurement; no unverified runtime flags were added.

Resume: changed reference assets, BAM preparation/alignment, caller wrappers and
resource-dependent commands can invalidate downstream tasks. Dorado basecalling
commands/resources are unchanged and remain cache-eligible when inputs, models,
container and original work/cache state match. Preserve the original run session
and S3 work directory. No infrastructure deployment is needed for these changes.

## Published layout

Variant results are organized under `<sample>/<category>/<caller>/`:

| Category | Callers |
| --- | --- |
| `germline` | bcftools, Clair3 |
| `somatic` | ClairS-TO, DeepSomatic |
| `structural` | Sniffles, Severus, Stellerator |
| `CNA` | DELLY (CNV), QDNAseq, SubChrom, ichorCNA |

Categories describe the analysis, not a confirmed biological origin in this
tumor-only workflow. Each caller retains its own original, target-filtered,
normalized and PASS outputs as applicable. NASVAR's combined multi-analysis
report remains together under `<sample>/nasvar/`. Alignment, QC and methylation
retain their existing directories.

All files within sample result directories contain the sample ID in their
basename. Files without it gain `<sample>.`, including nested logs, plots,
provenance and reports. For example, DELLY publishes
`<sample>/CNA/delly/<sample>.delly.bcf`, and DeepSomatic publishes
`<sample>/somatic/deepsomatic/<sample>.somatic.vcf.gz` plus its matching index.
QC is `<sample>/qc/<sample>.index.html`. Directory names are unchanged within
caller outputs. Local links in HTML/JSON/CSS/Markdown reports and the Classy audit
are adjusted to the published filenames. Scientific binary/table contents,
archive members and historical log text are preserved. Run-level outputs
(`manifest.json`, `pipeline_info`, basecalling and raw demultiplexing) retain
run-level naming. The manifest and top-level report use the new paths.

Publication renaming operates on copies. Existing computation work files keep
native tool names. This layout change reruns publication/report tasks; unchanged
upstream computations remain eligible for resume. Use a fresh output directory
when resuming into this layout: Nextflow does not remove files previously
published under the old layout.


Fixing runtime log capture changes the affected caller task scripts and therefore
reruns those tasks on resume. An exit-zero caller can still be marked failed if
required outputs are absent; repeated retries do not repair a logging wrapper
that creates files after output staging. Upstream preparation/alignment remains
cache-eligible when otherwise unchanged.
