# FrankONTstein contributor instructions

## Design
- Model Nextflow DSL2 organization on nf-core/oncoseq: main entrypoint, workflows,
  subworkflows, modules, conf, schemas, docs, and nf-test suites.
- Primary use is tumor-only ONT adaptive sampling; support hg38/GRCh38 and hs1/CHM13.
- Inputs are basecalled unaligned BAMs, or POD5 with explicit optional GPU
  basecalling. Matched normals and WGS orchestration remain outside scope.
- `--primary` (default): alignment/QC and methylation/Classy. `--secondary`: primary
  plus NASVAR coverage/MAF/karyotype/CNV/fusions/breakpoints. `--tertiary`: primary,
  full NASVAR and compatible oncoseq callers. Flags are mutually exclusive.
- Preserve MM/ML/MN tags and read groups. Demultiplex before optional trimming;
  never silently process a tag-stripped BAM as methylation-capable.
- Both `--targets_bed` and `--enrichment_bed` are required in every tier.
- Resolve relative reference/image-lock paths from projectDir; preserve legacy
  bundle-relative assets and launch-relative sample inputs.
- Keep `bam` (or `pod5` with `basecall`), `genome`, and `sample_id` on the command
  line in direct-input run examples.
- Prefer shared top-level run inputs and per-analysis assets under `steps`;
  retain legacy reference bundles. Auto-select NASVAR reference JSON by genome;
  auto-select the matching pediatric leukemia pipeline config as well.
- Separate enrichment BED from target BED and immutable genome assets. Reject
  incompatible explicit callers; report default exclusions. Never mix genome builds.
- Use standard public hg38 ichorCNA reference files and normal panel when no
  adaptive-sampling panel is available; record their provenance.
- Keep each caller's results distinct. Do not generate consensus calls implicitly.

## Dependencies and extension
- Pin oncoseq and NASVAR as Git submodules; never follow branch heads at runtime.
- Initialize only required oncoseq gitlinks: upstream has a stale sturgeon mapping.
- Own orchestration and resource config; reuse upstream processes where compatible.
- Keep custom wrappers in modules/local. Use [meta, bam, bai] channel conventions,
  preserve meta.id, emit versions and artifact outputs, and document prerequisites.
- Pin OCI images by digest for releases. Docker is used locally/AWS; Apptainer on
  Slurm. NASVAR's non-commercial license and all upstream notices must be retained.
- Update dependency lock, gitlinks, images, compatibility inventory, and affected
  tests together. Never modify the user's external source checkouts.

## QC
- All tiers produce indexed modkit CpG bedMethyl, retaining separate 5mC/5hmC.
- Comprehensive QC defaults on; disable_qc skips QC, not bedMethyl or Classy.
- Keep whole-genome/on-enrichment/off-enrichment/target denominators explicit;
  report MAPQ 0 and 20 coverage separately and null for undefined quantities.
- Large BAMs require streaming, bounded summaries and capped parallelism. Do not
  introduce per-read databases or full per-base intermediate tables.

## Validation and release
- Use strict Nextflow v2 syntax; test Nextflow 26 and keep vendor gitlinks unchanged.
  Keep callback helpers in lib/ and use explicit closures for dynamic publish paths.
- Test tier/caller resolution, sample identity, reference compatibility, tag integrity,
  empty calls, failures, and resume. Run affected Python/nf-test tests and small
  real-data integration tests; stubs alone do not establish scientific correctness.
- Run terraform fmt -check and validate; never apply infrastructure unless requested.
- Do not claim Slurm/AWS or classifier/model validation without an actual smoke run.
- Public examples contain no account identifiers, secrets, patient data, or models
  whose redistribution terms have not been checked.
