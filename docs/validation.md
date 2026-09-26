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

Parallel BAM validation checks serial/parallel QC equality across multiple batches,
reverse-strand records, and propagation of malformed MM errors from workers. A
local synthetic benchmark (12,000 reads, 8 kb/read, 2,000 modifications/read) took
2.56 s at 1 CPU, 1.04 s at 4 CPUs, and 0.57 s at 8 CPUs. This measures tag decoding
on synthetic data, not production storage or full pipeline throughput.

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
