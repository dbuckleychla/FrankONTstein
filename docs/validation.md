# Validation and release status

## Automated checks

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
- `tests/test_modbam.py`: real small BAM records created with pysam; checks reverse-strand alignment, lost tags, changed probabilities, unknown reads and stale trim coordinates.
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
