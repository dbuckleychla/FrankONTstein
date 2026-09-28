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
- Preserve MM/ML/MN tags and read groups. Demultiplex with barcode trimming enabled (never pass --no-trim to demux),
  before adapter/primer trimming (on by default);
  never silently process a tag-stripped BAM as methylation-capable.
- Both `--targets_bed` and `--enrichment_bed` are required in every tier.
- Resolve relative reference/image-lock paths from projectDir; preserve legacy
  bundle-relative assets and launch-relative sample inputs.
- Keep `bam` (or `pod5` with `basecall`), `genome`, and `sample_id` (singleton) or
  `experiment_id` (multiplexed with a demux sheet) on the command line in
  direct-input run examples. `run_id` independently labels AWS work/results paths.
- Prefer shared top-level run inputs and per-analysis assets under `steps`;
  retain legacy reference bundles. Auto-select NASVAR reference JSON by genome;
  auto-select the matching pediatric leukemia pipeline config as well.
- Separate enrichment BED from target BED and immutable genome assets. Reject
  incompatible explicit callers; report default exclusions. Never mix genome builds.
- Use standard public hg38 ichorCNA reference files and normal panel when no
  adaptive-sampling panel is available; record their provenance.
- Keep each caller's results distinct. The authorized exception is automatic NASVAR-query
  somatic consensus requiring exact normalized PASS alleles from both DeepSomatic
  and ClairS-TO. PGx and fusion evidence remain separate; no fusion consensus.
- Generate per-sample offline Quarto summaries in all tiers; distinguish unavailable
  analyses from zero calls. Stage only small work artifacts for reporting.

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

## Working agreement for human and LLM collaborators
- Read this file before editing. Inspect the current implementation and git diff;
  preserve unrelated or uncommitted work. Do not reset, clean, or rewrite existing
  work to obtain a clean checkout. Do not commit or push unless requested.
- Implement the requested change within the existing tumor-only scope. Do not add
  matched-normal analysis, consensus calling, new platforms, automatic model
  downloads, infrastructure deployments, or broad architectural rewrites as
  incidental improvements. Explicit user instructions may change this scope;
  update the relevant contracts and documentation with the implementation.
- Use existing helpers and conventions before adding parallel implementations.
  Keep scientific processing, orchestration, resource configuration, publication,
  and reporting separate. Do not move scientific computation into report scripts.
- Report what changed, what was tested, and remaining limitations. Distinguish
  static/config checks, stub routing, real-data tests, and actual GPU/cloud runs.
  Do not treat a successful stub or downloaded image as runtime validation.
- Inspect the exact pinned runtime before changing CLI flags or model assumptions.
  Record unresolved runtime bugs as TODOs with the affected behavior and evidence
  needed to remove the workaround. Do not silently restore a known-broken path.

## Architecture and files to update together
- `main.nf`: entrypoint, input validation, reference resolution and run provenance.
- `workflows/adaptive.nf`: tier orchestration and reporting; primary preprocessing
  is shared across tiers. `subworkflows/local/calling.nf`: independent caller
  branches, existing prerequisite relationships, filtering and artifact channels.
- `modules/local/`: owned Nextflow wrappers. `bin/`: task-side executables and
  focused Python helpers. `lib/`: shared Groovy validation, status and layout logic.
- `conf/base.config`: global resource/retry policy. `conf/modules.config`:
  process resources. `conf/profiles/`: executor and GPU routing. Avoid scattering
  resource settings or duplicating GPU selection rules in individual workflows.
- Parameter changes require matching `nextflow.config`, `nextflow_schema.json`,
  CLI help, examples and applicable validation/tests. Record relevant parameters
  in provenance. Maintain public documentation in `docs/` and `documentation/`.
- Caller additions/changes must update tier/build selection, image requirements,
  reporting, failure attribution, output categories and tests together. Preserve
  logical analysis names used by manifests even when publication paths change.
- Keep vendor gitlinks unchanged during ordinary workflow edits. Dependency/image
  upgrades are deliberate changes requiring lock/provenance and compatibility
  updates; never patch external sibling checkouts or vendor sources in place.

## Input identity and AWS directory contracts
- Singleton direct BAM/POD5 input uses `--sample_id` for the output sample.
  Multiplexed direct input uses `--experiment_id` with `--demux_samplesheet`;
  reject the old ambiguous use of `--sample_id` for pooled direct input.
- Demux sheets accept local or S3 CSVs. Require `experiment_id,kit,barcode,alias`;
  accept extra sequencer columns. Match experiment_id to the input run, and use
  alias for output sample identity. The sheet's sample_id column does not route
  samples. Preserve failures for missing requested barcodes and duplicate mappings.
- Input manifests retain `sample,run,bam` or `sample,run,pod5`; do not combine
  manifests with direct-input identity options. Accept one input type per run.
- `--run_id` is an execution-directory label supplied to Nextflow, independent of
  sample/experiment identity and the input directory basename. The AWS environment
  helper exports Terraform infrastructure settings and base work/results prefixes
  only; it must not choose or retain a run-specific suffix.
- AWS derives `<work_prefix>/<run_id>` and `<results_prefix>/<run_id>`. Explicit
  `-work-dir` and `--outdir` override defaults. Do not reintroduce the obsolete
  FRANKONTSTEIN_WORK_DIR/FRANKONTSTEIN_OUTDIR environment overrides. Preserve
  non-AWS profile behavior. Reuse the same work prefix/run ID and cache for resume.

## Adapter trimming contract
- Adapter/primer trimming defaults on. `--no-trim-adapter` disables only the
  separate TRIM_BAM step; demux always trims barcodes. Reject the removed --trim
  option with a migration message. Singleton inputs require sequencing_kit unless
  trimming is disabled; multiplexed inputs use the demux sheet kit.

## Basecalling, GPU and resource contracts
- POD5 basecalling is optional, NVIDIA-only, and requires explicit staged base
  and compatible CpG 5mC/5hmC modification models; no runtime model downloads.
  Resolve direct-child POD5 files deterministically, reject empty/duplicate inputs,
  stage collision-safe names, and round-robin sorted paths into
  min(basecall_tasks, file_count) batches. Default basecall_tasks is 16.
- Dorado emits unaligned, untrimmed BAMs with move tables (`--emit-moves`). Demultiplex
  each shard/input BAM independently for multiplexed runs, then trim adapters/
  primers independently per barcode BAM before merging by sample through CPU
  PREPARE_BAM (samtools cat, not merge) and running bounded checks. Align the prepared sample BAM. Missing
  barcodes fail across the entire run, not individual shards. Singleton inputs
  trim per shard/input BAM before PREPARE_BAM. --no-trim-adapter skips only trimming.
  Keep shard BAMs in work storage; publish basecalling logs/model provenance.
- One GPU per basecalling task: AWS accelerator 1 on aws_gpu_queue; Slurm one GPU
  on gpu_queue with Apptainer --nv; local Docker one explicit basecall_device.
  Verify GPU visibility and fail without CPU fallback. Default basecall_max_forks
  is 1 locally and 32 on schedulers; local tasks cannot share the selected device.
- Clair3 and DeepSomatic default to automatic GPU selection when an appropriate
  queue/device exists, otherwise CPU. Explicit false forces CPU. ClairS-TO remains
  CPU by default until a patched image resolves its documented GPU issue and is
  verified. Merely changing an image tag does not establish that it is fixed.
- Current starting budgets include alignment 32 CPUs/64 GB, Dorado 4 CPUs/16 GB
  per GPU task, and DeepSomatic 8 CPUs/64 GB. Respect global resource caps and
  measure larger runs before revising budgets; partial-run observations do not
  establish full-run requirements. More host RAM does not increase GPU VRAM.
- Global max_retries defaults to 2: one initial attempt plus two retries for failed
  process tasks, including exit 134. Zero disables retries. Keep this policy shared;
  preflight errors are not task retries. Retry placement on a fresh GPU is not
  guaranteed, and CUDA unknown-error/exit 134 alone is not proof of OOM.

- PREPARE_BAM concatenates compatible unaligned shards without recompression,
  unions RG/PG headers, and records exact source headers in cat_header.json.
  Conflicting RG/program identities or sequence dictionaries fail explicitly;
  varying PG command lines are retained in provenance. A single BAM bypasses cat.

## Scientific processing and publication contracts
- DeepSomatic is an independent hg38-only tertiary default, using ONT_TUMOR_ONLY,
  the exact target BED, and default PoN filtering. Exclude it from hs1 defaults
  with a status reason; reject explicit incompatible selection. No matched normal.
- bcftools pileup, Clair3 and DeepSomatic use targets_bed, without added padding.
  Do not silently substitute enrichment_bed or newly restrict other callers.
  Preserve enrichment_bed for QC, NASVAR and off-enrichment coverage/CNV. Existing
  buffers in a supplied target BED cannot be inferred or removed automatically.
- Retain caller-native and existing target-filtered outputs. Finalization adds
  indexed normalized VCFs and exact FILTER=PASS subsets where applicable. Dot
  means unassessed, never PASS. All-dot callsets record non-applicability; filtered
  all-fail callsets retain valid empty indexed PASS VCFs. Do not invent FILTER
  semantics for tables/JSON. Preserve separate caller results and sample labels.
- Publish variants under `<sample>/<category>/<caller>/` using OutputLayout:
  germline = bcftools/clair3; somatic = clairsto/deepsomatic;
  structural = sniffles/severus/stellerator;
  CNA = delly/qdnaseq/subchrom/ichorcna (DELLY currently runs CNV analysis).
  Categories do not establish biological origin in tumor-only data. Keep NASVAR's
  mixed report together under nasvar; alignment, QC and methylation retain their
  own directories. See documentation/variant-output-filtering.md.
- Every published sample-specific file basename must contain its sample ID,
  including nested logs, plots, reports and provenance. Rename publication copies,
  preserve working/native files and index pairings, and update local report links
  and manifest paths. Keep global/run-level artifacts separate. Do not rewrite
  scientific binary/table contents or archive members merely to rename files.
- Publication changes do not remove old files from an existing output destination.
  Explain cache implications and recommend a fresh output directory when changing
  layouts; preserve upstream cache eligibility where commands/inputs are unchanged.
- BAM preflight checks are intentionally bounded: quickcheck, header/read-group
  sanity and at most 1,000 records for required tag presence. Do not reintroduce
  exhaustive BAM scans or MM/ML/MN decoding/validation. Assume successful basecalling
  produces well-formed tags; consuming methylation tools report malformed data.
  This does not disable requested scientific QC or allow silent tag loss.
- Create required runtime logs inside each process script using the shared
  capture_task_logs.sh helper. Do not use afterScript to create declared outputs:
  AWS Batch output staging may occur before that hook. Preserve exit status,
  pipefail, console streaming and complete log writes before task exit.
- Run the Python Classy sidecar audit during publication in the preprocessing
  image; do not assume classy-slim contains python or python3.
- Preserve quality warnings, missing-Classy-sidecar audits and reference exclusion
  provenance. Do not silently discard incomplete results, impute undefined values,
  or turn research QC thresholds into clinical interpretations.

## AWS startup diagnostics
- Diagnose DockerTimeoutError during container creation separately from tool
  failures. No command ran; exit 134/CUDA and missing declared outputs are different
  failure classes. Do not assume OOM or fix startup by increasing task RAM blindly.
- Workers need no SSH/SSM access. Use bin/aws_batch_diagnostics.py for read-only
  AWS evidence. New-worker Terraform bootstrap forwards host journal, ECS and
  bootstrap logs to /<stack>/hosts and metrics to FrankONTstein/BatchHost.
- Preserve CPU/GPU parity in the shared launch template. gp3 performance is
  explicit/configurable and incurs cost above baseline. Do not add an AWS I/O
  concurrency cap; it was explicitly removed. Do not present storage tuning
  as a proven root-cause fix.
- Diagnostics require worker-role permissions and outbound access to CloudWatch
  and package/image sources. Never apply Terraform or terminate workers without
  explicit authorization; existing workers do not gain new bootstrap retroactively.

## Verification guide
- Use `.github/workflows/ci.yml` and `docs/validation.md` for executable checks;
  run affected Python tests, Nextflow 26 strict-syntax plan/config/routing checks
  and relevant nf-tests. Exercise sample identity, failure attribution, empty
  outputs, disabled QC, build restrictions and resume for affected branches.
- GPU routing/configuration probes must not submit cloud jobs. For scientific
  command changes, run small real-data integrations when inputs/runtime/hardware
  are available; explicitly report what cannot be exercised.
- For Terraform changes, run format/validation without applying. Read-only
  inspection does not authorize deployment, instance termination or IAM changes.
- Documentation-only changes require consistency/link review, not an unnecessary
  full scientific rerun. Keep this file aligned with intentional contract changes.
