# Somatic consensus and sample summaries

Every tier produces `<sample>/summary/<sample>.summary.html` and its JSON companion.
The HTML embeds rendering resources for offline viewing; the run index links to it.
Blood-domain cancer-classification results retain original labels, scores, cutoffs and
feature coverage. Scores are not averaged and controls/below-cutoff results remain visible.
QC separates MAPQ 0/20, genome, enrichment, off-enrichment and targets. Disabled/missing
analyses are not displayed as zero results.

When both DeepSomatic and ClairS-TO are selected, an independent CPU step produces:

- `<sample>/somatic/consensus/<sample>.consensus.snv.vcf.gz` and `.tbi`;
- corresponding `.consensus.indel.vcf.gz` and `.tbi`;
- `.consensus.evidence.tsv`, `.consensus.json`, and `.consensus.provenance.json`.

No enable flags are needed. Explicit caller selection remains authoritative. A single
caller, primary/secondary tiers, or hs1 cannot produce this two-caller consensus.
The summary reports it as unavailable. Required caller failures fail the run; missing
inputs must not be converted into a successful empty consensus.

## Scientific definition

Only exact `FILTER=PASS` from **both** somatic callers qualifies. Alleles are split and
left-normalized using the validated reference; reference mismatches fail. Matching uses
CHROM/POS/REF/ALT, with each caller contributing at most one vote. Dot is unassessed,
not PASS. Complex substitutions are not atomized; symbolic alleles and breakends are
excluded and counted. Independent caller outputs and existing finalization outputs
remain intact.

The query set uses `steps.nasvar.config` (or the legacy bundle/default configuration),
the matching `steps.nasvar.gff`, and NASVAR reference contig aliases. Pathogenic SNV
coding positions are mapped through the configured CDS and strand. Indel windows use
NASVAR's 1-based inclusive bounds, converted to 0-based half-open intervals. Membership
is normalized REF-span overlap including the anchor, with no padding. This includes
sequence-resolved small indels in those windows; it does not infer that each is an ITD
or matches the configured named mutation. Query labels are not protein annotations.
NASVAR read/frequency/length thresholds remain separate evidence, not additional filters
on other callers' PASS decisions. Required unmappable queries fail instead of disappearing.

Outputs are **tumor-only somatic candidates**, not proof of somatic origin. QUAL and GT
are missing rather than invented. Caller DP/AF are separate INFO fields; duplicate
inconsistencies leave the corresponding field missing. The evidence TSV retains filters,
QUAL, DP/AD/AF/VAF/GT where present, including singleton and discordant records. Empty
indexed VCFs are valid but do not establish confident reference genotypes. Clair3/bcftools
are not counted as consensus votes.

Pharmacogenomics uses NASVAR's reported findings separately and is excluded from somatic
consensus. Fusion evidence lists NASVAR and Stellerator candidates separately. It does
not match gene pairs/breakpoints or produce fusion consensus counts/VCFs. Large structural
ITDs remain outside the small-indel consensus.

## Rendering image and resources

Both new tasks request 2 CPUs and 4 GB, respecting global caps and retries. The renderer
stages only selected JSON/TSV files from work channels, never BAMs or published-directory
globs. Existing upstream tasks remain eligible for `-resume`; new consensus/report tasks
run and report/index publication changes may rerun.

Build `docker/summary/Dockerfile` for linux/amd64. It extends the pinned preprocessing
image and installs Quarto **1.7.31** at build time. The Docker build includes an HTML
rendering smoke test. No packages are downloaded by workflow tasks. Add the verified
published digest as `summary` in the image manifest; mutable tags are rejected before
scheduling. The container release workflow builds it and `bin/lock_images.py` now requires
`--summary IMAGE` alongside `--preprocess` and `--nasvar`.

A real rendering image digest is required before deploying this change. Python and stub
tests do not establish that the registry image renders successfully.

## Validation

Run `python3 -m unittest discover -s tests` with pysam 0.23.3 and Quarto available,
`python3 tests/run_contracts.py`, `python3 tests/run_consensus_contracts.py`, and
`nf-test test tests/consensus.nf.test` using Nextflow 26 strict syntax. Tests cover allele
representations, filtering, query mapping, sample identity, empty results, caller exclusions,
failure attribution and resume. Quarto-dependent tests explicitly skip with a reason
when rendering is unavailable in a sandbox.
