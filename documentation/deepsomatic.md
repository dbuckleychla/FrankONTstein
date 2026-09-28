# DeepSomatic tumor-only ONT calling

DeepSomatic is an independent default tertiary caller on hg38/GRCh38. It uses
`ONT_TUMOR_ONLY` with default PoN filtering, without a matched normal. hs1 is
excluded from defaults in this initial integration; explicitly requesting it
on hs1 fails. Explicit `--callers` lists control inclusion as usual.

```bash
nextflow run . -profile aws -params-file references.hg38.yaml \
  --tertiary --callers deepsomatic \
  --bam s3://YOUR_BUCKET/sample.bam --no-trim-adapter --sample_id sample1 --genome hg38
```

The reference YAML must supply the required reference FASTA/index, target and
enrichment BEDs, and pinned image manifest. Existing AWS queue/role/work settings
are also required. For POD5, use `--basecall --pod5` instead of `--bam` with the
existing explicit Dorado model configuration.

## Regions and execution

`--regions` receives `targets_bed`, exactly as supplied, with no added buffers.
Clair3 and bcftools calling restrictions now use the same BED. Enrichment remains
separate for QC, NASVAR and off-enrichment coverage/CNV processing. DeepSomatic
does not depend on Clair3 or ClairS-TO. A separate downstream step produces
[NASVAR-query consensus](consensus-summary.md) when DeepSomatic and ClairS-TO are both selected.

One wrapper task handles example generation, inference and postprocessing.
`--deepsomatic_cpus 8` controls CPUs and `--num_shards`; host RAM defaults to
`--deepsomatic_memory '64 GB'`. Global resource caps apply, and RAM scales with
the existing retry policy. These defaults require performance measurement.

`--deepsomatic_gpu auto` uses the configured AWS/Slurm GPU queue or local Docker
`--basecall_device`. One GPU is reserved for the entire scheduler task, including
CPU-heavy stages. `false` forces CPU execution and hides CUDA devices; `true`
requires valid GPU configuration. GPU mode checks TensorFlow GPU visibility.
Local device exposure does not provide cross-process exclusive GPU scheduling.

## Outputs and validation

Each sample gets separate `<sample>/somatic/deepsomatic/` outputs: `<sample>.somatic.vcf.gz` and index,
logs, provenance, and the existing target-filtered VCF/index. Intermediates stay
in work storage. Empty variant sets with valid VCF headers/indexes are accepted;
missing output files or nonzero caller exits fail explicitly. Separate indexed normalized and exact-PASS subsets are added for both raw and target-filtered VCFs; originals remain available. Provenance records
the image, checked runtime version, model type, bundled model/PoN checksums,
PoN setting, target BED checksum, sample, command,
GPU mode, CPUs and shards. Software versions join the normal run report.

Use an explicit original session UUID when resuming. Adding this caller does
not require new basecalling; changing region restrictions invalidates affected
bcftools/Clair3 task caches. Logs from failed tasks remain in work storage.

## Release acceptance

Target release: official DeepSomatic 1.10.0 (latest stable in the supplied
DeepVariant release metadata, published 2026-03-05). The official GPU-capable image is pinned to
`sha256:7f201540f3b267099c3f3cdcd4164798b58cca36ee89fd55fc56991cd82f1c31`.
The user-extracted image inventory confirms the bundled ONT tumor-only
SavedModel, example-info files, and PoN VCFs/indexes. The extracted Python
entrypoint confirms the requested CLI flags, ONT model selection and default
ONT PoN (`PON_dbsnp138_gnomad_PB1000g_pon.vcf.gz`). Each task checks the bundled
assets and runtime version before inference. Executable and actual inference
validation remain separate from source inspection.
No runtime model downloads are permitted. Real CPU/GPU model inference and
scientific accuracy are not established by the stub routing tests.
