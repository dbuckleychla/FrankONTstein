# Optional POD5 basecalling

`--basecall` adds GPU Dorado basecalling before the normal BAM workflow in every
tier. BAM input remains the default. Use one input type per invocation; FAST5,
FASTQ, live acquisition, duplex calling and automatic model downloads are not
supported.

## Inputs

Use `--pod5 FILE_OR_DIRECTORY --sample_id SAMPLE --genome hg38`, or `--input`
with a CSV containing `sample,run,pod5`. Paths may be local or S3 URIs. Directories
select only direct-child `*.pod5` files, not nested directories. Multiple rows
for the same sample combine its chunks. In multiplexed mode rows group by run;
`--demux_samplesheet` accepts the sequencer export with required columns
`experiment_id,kit,barcode,alias`. `experiment_id` matches the input run ID;
`alias` names the output sample. A direct invocation’s `--sample_id` must match
`experiment_id`. Extra columns (including the sheet’s `sample_id`) are optional
and ignored for routing. One kit
per run and unique sample/barcode mappings remain mandatory.

POD5 paths resolve relative to the launch directory. Duplicate resolved files,
including overlapping file/directory entries, are rejected. Files with matching
basenames in different directories are staged under distinct names.

## Offline models

Provide these assets in a parameters YAML, alongside your existing reference
settings (or with `--reference_bundle`):

```yaml
steps:
  basecall:
    model: /models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0
    modified_models:
      - /models/dna_r10.4.1_e8.2_400bps_sup@v5.2.0_5mCG_5hmCG@v2
```

Paths identify complete, pre-downloaded model directories, retaining their
canonical versioned Dorado names, `config.toml`, and tensor weights. Relative
model paths resolve from `projectDir`. The first implementation accepts R10.4.1
E8.2 400bps DNA models and exactly one matching combined CpG 5mC/5hmC model.
The example illustrates naming; supply model versions available for and
compatible with your pinned Dorado image and sequencing chemistry.

A CPU preflight checks assets, model pairing, checksums and required Dorado CLI
options. Dorado then validates model loading and POD5 compatibility during the
GPU task. Neither stage downloads models or falls back to CPU.

`--basecall_model sup|hac|fast` continues to select the **Clair3** model. When
Clair3 is selected, including implicitly through SubChrom, POD5 calling requires
a matching SUP/HAC v5.0.0 model when using bundled weights. To use Dorado v5.2.0,
set `steps.clair3.model` to a local or S3 directory named
`r1041_e82_400bps_sup_v520_with_mv` (or the corresponding HAC directory), containing
`pileup.pt` and `full_alignment.pt`. The workflow stages these weights, validates
accuracy/version pairing with `--basecall_model`, records their checksums, and
passes `--enable_move_table` to Clair3. Relative model paths resolve from projectDir.
Move-aware models require valid `mv` tags; existing preprocessing scans reject
missing/stale move tables. The pinned Clair3 runtime must expose
`--enable_move_table`; actual model/runtime compatibility still needs a smoke run.

## GPU execution

| Backend | Required configuration | Basecalling allocation |
| --- | --- | --- |
| Local NVIDIA/Linux | `-profile local,docker --basecall_device 0` (index or GPU UUID) | Docker exposes only the selected GPU; one task at a time |
| Slurm | `-profile slurm,apptainer --gpu_queue GPU_PARTITION` | `--gres=gpu:1`, Apptainer `--nv` |
| AWS Batch | `-profile aws --aws_gpu_queue GPU_QUEUE` plus normal AWS parameters | One accelerator on the GPU queue |

The scheduler queue/partition must be configured for NVIDIA GPUs. Merely naming
a queue does not establish hardware availability: each task verifies visibility
with `nvidia-smi`, then explicitly uses CUDA. Scheduler CUDA visibility masks are
preserved. Do not override GPU allocation or container settings with CPU-only
site selectors. Apple Silicon/Metal and CPU basecalling are not supported.

`--basecall_tasks` defaults to 16 per input group. Sorted POD5 paths distribute
round-robin into at most that many nonempty batches. `--basecall_max_forks`
defaults to 32 on schedulers and must be 1 locally. Each task uses one GPU;
standard CPU/memory/time limits still apply. CPU preparation, demultiplexing,
trimming and alignment retain their existing queues. Clair3 GPU selection is
independent.

## Data flow and outputs

Dorado emits unaligned, untrimmed BAM shards with modification tags and read
groups. Shards merge on CPU through `PREPARE_BAM`, then enter existing
sample demultiplexing, optional trimming, alignment, QC and analysis. Unclassified
BAMs retain the existing demultiplex output behavior. Disabling QC does not skip
modification-tag checks, Classy or indexed CpG bedMethyl.

Shards remain in Nextflow work storage. `basecalling/<input-group>/batch_*.log`
contains task logs and visible GPU UUIDs. GPU UUIDs, chunk start/completion messages,
and Dorado stderr are also streamed to the task console (CloudWatch on AWS Batch);
BAM stdout is written only to the shard file. With shell pipefail enabled, logging
through tee preserves a Dorado failure. `basecalling/models.json` records
Dorado's version and SHA-256 content fingerprints of both model directories.
The run manifest links these artifacts per sample and records input/model paths,
image digest, GPU settings and batching parameters. Failed multiplexed
basecalling tasks mark the mapped samples' basecalling status as failed.

`-resume` reuses completed batches. Keep POD5 inputs immutable; model preflight
uses content hashing so changed model contents invalidate dependent basecalling.

## Examples

Keep the existing BAM commands for pre-basecalled input. For singleton POD5:

```bash
nextflow run . -profile local,docker -params-file references-and-models.yaml \
  --basecall --pod5 /data/run/pod5 --sample_id sample1 --genome hg38 \
  --basecall_device 0 --targets_bed targets.bed --enrichment_bed enrichment.bed \
  --image_manifest images.lock.json --outdir results/sample1
```

For multiplexed POD5 on Slurm:

```bash
nextflow run . -profile slurm,apptainer -params-file references-and-models.yaml \
  --basecall --pod5 /data/run/pod5 --sample_id run1 --genome hg38 \
  --demux_samplesheet demux.csv --gpu_queue GPU_PARTITION --slurm_queue CPU_PARTITION \
  --targets_bed targets.bed --enrichment_bed enrichment.bed \
  --image_manifest images.lock.json --outdir results/run1
```

The parameters file must also supply the normal FASTA/reference assets. All
analysis tiers still require both BEDs. Add `--secondary` or `--tertiary` with
compatible callers as for BAM input.

Dorado basecalling always enables `--emit-moves`, recording move tables (`mv`)
in the unaligned BAM shards alongside modification tags. Model preflight checks
that the installed Dorado exposes this option. This adds metadata without
changing the called sequence. Existing chunks generated without this option
must be basecalled again to obtain move tags; the changed task script invalidates
their previous cache entries. Select matching external Clair3 weights with `steps.clair3.model` as described above.

## Per-chunk resources

Each Dorado chunk requests one GPU, `--basecall_cpus 4` and
`--basecall_memory '16 GB'` by default. Global `--max_cpus` and `--max_memory`
still cap these requests. Host RAM doubles on the existing single retry;
this does not change GPU VRAM. CPU preprocessing retains its existing resources.

For g6, start with g6.2xlarge (8 vCPUs, 32 GiB host RAM); for g6e,
g6e.xlarge (4 vCPUs, 32 GiB host RAM) fits the default request. A g6.xlarge
has only 16 GiB host RAM, so a 16 GB task request leaves insufficient OS/ECS
headroom. An experimentally reduced request such as `--basecall_memory '12 GB'`
may fit, but must be validated against actual peak RSS. A 32 GB retry likewise
needs a larger instance than one with exactly 32 GiB physical RAM.

These are initial resource budgets, not measured performance optima. Compare
GPU utilization, peak host RSS, throughput and cost on the same input before
reducing further; increase CPUs if input/output processing starves the GPU.
`--basecall_max_forks` controls concurrency independently. Resource-only edits
normally preserve task cache keys; the Dorado command is unchanged by this tuning.
