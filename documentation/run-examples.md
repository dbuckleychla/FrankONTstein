# FrankONTstein run examples

Use Nextflow 26.04.6 and Docker for the local examples below. Launch from the
FrankONTstein repository directory unless an example says otherwise. These are
commands to adapt to your data; they are not claims of biological validation.

## Reference setup and path rules

Copy `assets/references.example.yaml` to `references.hg38.yaml` and edit the paths.
Keep the downloaded `images.lock.json` in the workflow directory. Supply `bam`,
`genome`, and `sample_id` on the command line, not in the reusable reference file.

- Relative reference paths in YAML resolve from the directory containing `main.nf`.
- The `-params-file` path, BAM/sample-manifest paths, output directory and work
  directory resolve from the launch directory.
- Use unaligned, basecalled BAMs containing valid modified-base tags.
- Both target and enrichment BEDs are required. Clip enrichment padding to FASTA
  boundaries before running; the checker does not alter your BED files.
- Primary is the default. Specify only one of `--primary`, `--secondary`, `--tertiary`.
- Task prefixes reflect analysis levels: `PRIMARY:ALIGN` and `PRIMARY:CLASSY_COMBINED`
  in every run, `SECONDARY:NASVAR` in secondary mode, and `TERTIARY:NASVAR` plus
  `TERTIARY:CALLING:...` in tertiary mode. Publication uses `REPORTING:...`.
  Classy products are under
  `<outdir>/<sample_id>/methylation/classy/`.

See [reference preparation](../docs/references.md) and
[public reference sources](../docs/reference-sources.md).

## 1. Primary: alignment, QC and Classy

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --bam /data/BC3.bam --genome hg38 --sample_id BC3 \
  --primary \
  --outdir results/BC3_primary \
  -work-dir work/BC3_primary
```

## 2. Primary with Dorado trimming

Use the actual sequencing kit used for the library; `SQK-LSK114` is an example.
Trimming is off by default and requires a kit before analysis can start.

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --bam /data/BC3.bam --genome hg38 --sample_id BC3 \
  --primary --trim --sequencing_kit SQK-LSK114 \
  --outdir results/BC3_primary_trimmed \
  -work-dir work/BC3_primary_trimmed
```

## 3. Secondary: add NASVAR CNV and SV analysis

Includes NASVAR coverage, MAF, karyotype, CNVs, fusions and breakpoint analysis.
NASVAR's pediatric leukemia config and reference JSON are selected automatically
by genome. Its repeats, SNP sites and GFF3 must be configured in the YAML.

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --bam /data/BC3.bam --genome hg38 --sample_id BC3 \
  --secondary \
  --outdir results/BC3_secondary \
  -work-dir work/BC3_secondary
```

## 4. Tertiary: full stack

Runs full NASVAR, including SNVs/ITDs, and all compatible oncoseq caller branches.
Configure all selected caller assets in the reference YAML. Results stay separate.

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --bam /data/BC3.bam --genome hg38 --sample_id BC3 \
  --tertiary \
  --outdir results/BC3_tertiary \
  -work-dir work/BC3_tertiary
```

To narrow the tertiary caller set, add, for example:

```bash
--callers nasvar,clair3,sniffles
```

Primary analyses remain enabled. `subchrom` automatically adds its Clair3
prerequisite. Selecting NASVAR in tertiary mode runs its full pipeline.

## 5. CHM13

Prepare a separate `references.chm13.yaml` with matching CHM13v2.0/hs1 assets.
Changing `--genome` alone does not replace paths in the reference file.

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.chm13.yaml \
  --bam /data/BC3.bam --genome CHM13 --sample_id BC3 \
  --tertiary --callers nasvar,sniffles \
  --outdir results/BC3_chm13 \
  -work-dir work/BC3_chm13
```

QDNAseq, SubChrom and ichorCNA are excluded for CHM13; explicitly requesting
one fails preflight. Other callers still require compatible assets.

## 6. Multiple samples or BAM chunks

Create `samples.csv`. Repeat a sample ID to combine its chunks:

```csv
sample,run,bam
BC3,run1,/data/BC3.part1.bam
BC3,run1,/data/BC3.part2.bam
BC4,run2,/data/BC4.bam
```

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --input samples.csv --genome hg38 \
  --secondary \
  --outdir results/batch_secondary \
  -work-dir work/batch_secondary
```

Use `--input` instead of `--bam`; sample IDs come from the CSV.

## 7. Demultiplex a pooled run, then trim

Create `pooled.csv`:

```csv
sample,run,bam
pool1,run1,/data/pooled.part1.bam
pool1,run1,/data/pooled.part2.bam
```

Create `demux.csv` using your actual kit and barcode assignments:

```csv
run,kit,barcode,sample
run1,SQK-NBD114-24,barcode01,BC3
run1,SQK-NBD114-24,barcode02,BC4
```

```bash
nextflow run . \
  -profile local,docker \
  -params-file references.hg38.yaml \
  --input pooled.csv --demux_samplesheet demux.csv --genome hg38 \
  --secondary --trim \
  --outdir results/demultiplexed \
  -work-dir work/demultiplexed
```

The kit comes from the demux sheet. Demultiplexing precedes trimming; unclassified
reads are retained separately. Missing barcodes fail explicitly. Omit `--trim`
if trimming is not wanted.

## 8. Resume from another launch directory (EC2 example)

From `/home/ec2-user/work`, with the workflow in `/home/ec2-user/FrankONTstein`:

```bash
nextflow run ../FrankONTstein/main.nf \
  -profile local,docker \
  -params-file ../FrankONTstein/assets/ec2_test_references.yaml \
  --bam "$PWD/BC3.bam" --genome hg38 --sample_id BC3 \
  --primary \
  --outdir ./results \
  -work-dir ./nxf_work \
  -resume
```

Omit `-resume` for the first run. Keep the launch directory, `.nextflow` cache,
work directory and run inputs available. Changed task names, scripts or inputs
may rerun affected tasks. Update the YAML to your clipped enrichment BED if needed.

## 9. Limit local resources or override a task

Add limits to any local command:

```bash
--max_cpus 8 --max_memory '24 GB'
```

These cap each task's request, not total workflow concurrency. For task-specific
overrides, create `resources.config`:

```groovy
process {
    withName: CLASSY_COMBINED {
        cpus = 8
        memory = '16 GB'
    }
}
```

Add `-c resources.config` to the command. Explicit overrides bypass caps unless
cap logic is included. Default alignment/threaded callers request 16 CPUs/32 GB;
Classy requests 8 CPUs/8 GB and NASVAR 8 CPUs/32 GB.

## 10. Slurm with Apptainer

Use paths shared between the coordinator and compute nodes, and replace the
queue/account values with your site's settings.

```bash
nextflow run . \
  -profile slurm,apptainer \
  -params-file references.hg38.yaml \
  --bam /shared/data/BC3.bam --genome hg38 --sample_id BC3 \
  --secondary \
  --slurm_queue YOUR_PARTITION --slurm_account YOUR_ACCOUNT \
  --outdir /shared/results/BC3_secondary \
  -work-dir /shared/work/BC3_secondary
```

Omit `--slurm_account` if your site does not use accounts. Configure a persistent
Apptainer cache. A representative Slurm run remains required for backend validation.

## 11. AWS Batch

Use the queue, region, role and bucket values from your Terraform outputs.
Prepare `references.aws.hg38.yaml` with accessible S3 reference paths and a local
`images.lock.json` on the coordinator. The task role needs access to input,
reference, work and output objects. Reference models stored as directories need
an arrangement Nextflow can stage from S3.

```bash
nextflow run . \
  -profile aws \
  -params-file references.aws.hg38.yaml \
  --bam s3://YOUR_INPUT_BUCKET/BC3.bam --genome hg38 --sample_id BC3 \
  --secondary \
  --aws_region YOUR_REGION \
  --aws_queue YOUR_BATCH_QUEUE \
  --aws_job_role arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_JOB_ROLE \
  --outdir s3://YOUR_OUTPUT_BUCKET/frankONTstein/results/BC3_secondary \
  -work-dir s3://YOUR_OUTPUT_BUCKET/frankONTstein/work/BC3_secondary
```

Run the coordinator on a persistent host; retain its launch/cache state for
`-resume`. This command does not provision infrastructure. See
[AWS setup](../docs/aws.md); live Batch execution still requires validation.

## 12. Routing tests without biological inputs

From the repository root:

```bash
python3 tests/run_contracts.py
```

This exercises all tiers and resume using stubs and mock callers. It does not
run the real analysis containers. Use `--skip-resume-check` only when deliberately
checking routing without cache reuse.

## CpG export and QC

Every tier now exports CpG bedMethyl and runs QC by default. To retain CpG output
and Classy while skipping comprehensive QC:

```bash
nextflow run ./main.nf -profile local,docker -params-file references.yaml \
  --bam /data/sample.bam --sample_id sample --genome hg38 \
  --primary --disable-qc true --outdir results -resume
```

See [QC outputs and metric definitions](qc.md) for on/off-enrichment coverage,
read lengths, CpG summaries and large-BAM execution costs.
