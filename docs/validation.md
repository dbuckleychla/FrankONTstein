# Validation and release status

## QC extension validation

Numerical tests use real pysam-generated BAMs and samtools depth to check mapped
fractions, exact length statistics, overlapping BED denominators, deletion
handling, MAPQ strata, CpG beta/depth denominators, missing 5hmC and zero coverage.
The QC CLI test creates indexed BGZF bedMethyl and generates JSON/TSV/HTML.
A local synthetic BAM/depth benchmark (10,000 reads of 10 kb over two contigs;
100 Mb query sequence) took 5.77 seconds with a 2-CPU budget and 3.35 seconds
with a 4-CPU budget, with identical metrics. This does not measure modkit,
production BAM sizes, or network-storage throughput. These
fixtures are synthetic; they are not biological validation of modification calls.

Run the production-image smoke test on a Docker-capable Linux host:

```bash
python3 tests/run_qc_container_smoke.py --image-manifest images.lock.json
```

This runs actual modkit on synthetic modified-base reads, indexes its output and
runs the QC suite. Local Docker access was unavailable during implementation;
the production-image smoke and representative large-BAM runtime/memory benchmark
remain unverified. Stub contracts cover all tiers, QC disabled, and resume.

## Automated checks

BAM input checks are now bounded to 1,000 records and do not decode modification tags. Tests cover tag presence, explicitly trusted malformed encoding, sampled-versus-complete yield labels, and preservation of read-group IDs/tags during sample reheadering. VCF tests cover PASS versus dot semantics, all-fail/empty indexed outputs, multisample rejection/selection, and QDNAseq contig normalization. Reference/Classy tests cover explicit exclusions and missing sidecar reporting.

### Nextflow 26 migration (2026-09-22)

Validated using Nextflow 26.04.6 from the local conda environment with its default
strict parser: all three tier routing contracts and their `-resume` cache checks
passed. Injected NASVAR exit 42 propagated and produced the expected failed
analysis manifest. Local/Docker, Slurm/Apptainer, and AWS configuration profiles
loaded successfully. All 14 Python tests and 34 Groovy assertions passed.
The pinned upstream module checkouts were unchanged. CI now targets both
25.10.2 with parser v2 and 26.04.6.

These are stub/mock routing and configuration checks, not real biological or
remote-backend execution. Native 26.04.6 resume passed; the older cache limitation
recorded below concerned the earlier 25.10.2 Java-jar test environment.

- `tests/plan.groovy`: tier selection, prerequisites, aliases, incompatibilities and identifiers.
- Python unit tests: coordinates, samplesheets, NASVAR error detection/section preservation, and report escaping.
- `tests/test_modbam.py`: small BAM records created with pysam; checks missing tags, stale trim coordinates, malformed modification encoding and serial/parallel QC agreement, including reverse-strand records.
- `tests/run_contracts.py`: all three analysis graphs, demultiplexing, optional trimming, output grouping and cache reuse, using explicit stub data and mock upstream executables. It never runs biological callers.
- Terraform formatting and provider validation.

The artificial BAM in `tests/fixtures/stub.bam` is intentionally **not a real BAM** and must only be used with `-stub-run`. Test images are intentionally unresolvable and must never be used as production image references. Output manifests record `stub: true` for stub runs.

Run `python3 -m unittest discover -s tests -v`; install pysam to avoid skipping BAM tests. To use a cached Nextflow distribution, pass `--nextflow-jar /path/to/nextflow-one.jar` to the contract runner. Run `FRANKONTSTEIN_TEST_ROOT="$PWD" nf-test test tests/reference.nf.test` for the process-level reference test.

## Required biological/backend acceptance

### Implementation check record (2026-09-21)

- Passed: 12 Python tests (including all seven pysam BAM tests), 23 Groovy assertions,
  dependency commit/gitlink checks, and Terraform formatting.
- Three-tier routing has passed with stub data and mock executables. These checks
  do not execute the real classifier or variant callers.
- Resume remains unverified locally: cache reuse also failed in an isolated
  one-process Nextflow reproducer in this execution environment. Run the contract
  suite without `--skip-resume-check` in a normal terminal or CI before release.
- A user terminal run of Terraform validation passed before the final AWS CLI,
  logging, and optional GPU additions. Validation of that final configuration is
  pending; the sandbox cannot start the provider subprocess.
- Production image builds/digest locking, real Classy/caller fixtures, nf-test,
  Slurm, and AWS smoke runs remain pending. No live infrastructure was deployed.

Before publishing a validated release:

1. Build actual Linux images, resolve their digests, retain licenses and verify all expected executables/models/assets.
2. Run small, deidentified or public modified-base uBAM fixtures for hg38 and CHM13. Verify alignment coordinates, MM/ML/MN integrity, read groups and Classy output against the selected upstream versions.
3. Test real barcoded input with trimming on/off, unclassified reads, absent barcodes, multiple chunks, malformed tags and duplicate read IDs.
4. Compare NASVAR secondary sections and tertiary pipeline output with direct pinned NASVAR runs, including no-variant results and low-coverage failures.
5. Validate all compatible caller branches using appropriate panel assets. Benchmark off-target CNV assumptions against assay controls; do not mistake contract tests for scientific validation.
6. Run representative Slurm/Apptainer and AWS Batch jobs, including cache reuse and interruption handling. Verify both Terraform network modes and data-retaining teardown procedures.
7. Release a tested image lock and reference-bundle IDs, plus the software/backend compatibility record.

Clinical validation and regulatory qualification are not provided by these software tests.

### Optional POD5 basecalling

`tests/run_basecall_contracts.py` exercises singleton and multiplexed POD5 routing, all tiers, trimming, QC-disabled behavior, deterministic batching, duplicate rejection and resume using stubs. `tests/test_basecalling.py` verifies offline model pairing, Clair3 compatibility and content checksums. `tests/plan.groovy` covers GPU/input preflight and multiplexed failure attribution. Run `nf-test test tests/basecalling.nf.test` for the batching wrapper.

Real acceptance additionally requires small consented/public singleton and multiplexed POD5 data, compatible local models and an NVIDIA host: run each through alignment, Classy and indexed bedMethyl; verify MM/ML/MN and read groups, both 5mC and 5hmC, barcode identity and resume. Record image/model checksums and hardware/backend. Slurm/AWS and classifier/model validation must only be claimed after actual smoke runs.

Basecalling implementation checks (2026-09-25): Nextflow 26.04.6 strict-parser
planning checks, all BAM and POD5 tier/resume contracts (including multiplexed
failures and colliding POD5 basenames), 28 Python tests, Slurm/AWS config parsing,
dependency-lock checks and `terraform fmt -check` passed. The nf-test wrapper was
run directly with Nextflow; the nf-test CLI was unavailable locally. Real
Dorado/model/GPU, Slurm and AWS execution remain unvalidated: the development
host has no NVIDIA device and its Docker daemon was stopped. Terraform validate
could not start its provider in the sandbox; the unsandboxed retry was blocked
by an approval-service error. No infrastructure was applied.

DeepSomatic acceptance additionally requires a real hg38 ONT tumor-only smoke
run using `ONT_TUMOR_ONLY` and default PoN filtering, validating VCF sample
identity/indexing, target restriction, PoN evidence, CPU/GPU behavior and failure
reporting. Stub routing is not inference validation. `test_bcftools_regions.py`
uses real bcftools and an indexed synthetic BAM to check target boundaries and
exclude reads in enrichment-only regions.

### Output-review mitigations (2026-09-26)

55 Python tests pass, including exact-PASS versus unassessed FILTER handling,
empty indexed outputs, sample-header preservation and reference/Classy audits.
Local finalization of real copied DeepSomatic, QDNAseq, DELLY, Sniffles,
ClairS-TO and empty Stellerator VCF/BCF outputs matched their existing PASS
counts and produced usable indexes and expected sample labels. This validates
postprocessing, not fresh caller inference or biological accuracy.
Nextflow 26 strict-parser BAM/POD5 tier, multiplexing, QC-disabled and resume
contracts pass with stubs; GPU-routing and CPU/RAM-cap configuration probes
pass for AWS, Slurm and local without scheduling jobs. The finalization
nf-test workflow was exercised directly with Nextflow; nf-test CLI is unavailable.
Resource changes require a production benchmark. Terraform fmt passes; validate
cannot load the local AWS provider schema because its plugin fails to start.
No infrastructure was applied, and vendor dependency checks pass unchanged.

## Task retries

All processes use `errorStrategy = 'retry'` with `--max_retries 2` by default:
one initial attempt plus up to two retries per task. This includes non-OOM
failures such as CUDA exit 134. Set `--max_retries 0` to disable retries.
A task that exhausts retries still fails the workflow. Preflight/configuration
errors are not process tasks and are not retried. Resource caps still apply;
retrying does not guarantee placement on another worker or GPU.

Consensus and summary validation: `tests/test_somatic_consensus.py` exercises real
VCF normalization, PASS agreement, query coordinates and indexed output;
`tests/test_sample_summary.py` checks identity, availability, escaping and actual
Quarto rendering when available. `tests/run_consensus_contracts.py` tests caller
selection, hs1 exclusion, disabled QC and process failures with stubs.
`tests/consensus.nf.test` checks module sample isolation; the existing tier/resume
contracts include both new processes. Quarto/container and real reference-dependent
validation must be reported separately from successful stub tests.
