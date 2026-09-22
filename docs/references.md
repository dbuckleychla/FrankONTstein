# Reference bundles

See [public reference sources](reference-sources.md) for a field-by-field download
inventory, the ichorCNA files already available in the pinned checkout, and assets
that must be prepared for your panel.

The reusable reference configuration is shown in `assets/references.example.yaml`: shared
reference inputs at the top level and per-analysis assets in `steps`. Supply
`--bam`, `--genome`, and `--sample_id` on the command line. The file's reference
paths must match that genome; changing `--genome` does not replace those paths. A separate bundle is
optional. For this layout, `fai` defaults to `<fasta>.fai`, and relative paths are
resolved from the workflow directory containing `main.nf` (`projectDir`). This
also applies to target/enrichment BEDs, the image lock, and the path to a legacy
bundle. Assets inside a legacy bundle still resolve relative to that bundle.
Absolute paths and supported remote asset URLs remain unchanged. BAM and sample
manifest paths retain their launch-directory semantics. The `-params-file` YAML
path itself is resolved by Nextflow from the launch directory.

NASVAR reference JSON defaults are selected from the pinned submodule:
`hg38`/`GRCh38` selects `GRCh38_reference.json`; `hs1`/`CHM13` selects
`T2T-CHM13v2.0_reference.json`. No download is required after bootstrap.
The pediatric leukemia pipeline config is also automatic:
`peds_leukemia_config.GRCh38.json` for hg38, or `peds_leukemia_config.json` for
CHM13. Repeats, sites and GFF remain explicit assets. Optional
`steps.nasvar.config` and `steps.nasvar.reference` paths override these defaults.
Legacy bundles support the same automatic selection when `nasvar.config` or
`nasvar.reference` is omitted. The following describes that legacy layout.

Start from `assets/reference_bundle.example.json`. Set `schema_version: 1`, a versioned `id`, and `genome` (`hg38` or `hs1`). The selected `--genome`, if supplied, must agree with the bundle. CHM13 v1.1 and v2.0 are not interchangeable assets.

The bundle requires uncompressed FASTA and its FAI. Relative paths resolve against the bundle's location; absolute paths and S3 URLs are also accepted. Each run uses one bundle; run different builds separately. Input/index basenames must match (`reference.fa` / `reference.fa.fai`). The reference-validation process checks FASTA offsets and line widths against its FAI, then checks BED/GFF/site coordinates against contig lengths.

The target BED and enrichment BED are always CLI inputs, never inferred from each other or from a genome bundle. BED coordinates are zero-based half-open. GFF3 and NASVAR site coordinates are one-based. Headers in the sites TSV are not supported. The FASTA index must contain chr1–chr22, chrX and chrY. Coordinate checks cover
shared contigs; annotation-only contigs are reported and skipped during validation
without modifying the input. Each asset must have at least one matching record.
NASVAR GFF3 and SNP-site coordinates can use chromosome aliases declared in its
selected reference JSON (for example NC_000001.11 versus chr1). The workflow
passes that JSON to preflight using `--reference-config`. BED inputs still use
FASTA contig names. Validation never rewrites or lifts over the files. GFF3
requires nine tab-separated columns; spaces inside fields are preserved.

| Analysis | Bundle assets |
| --- | --- |
| All tiers | `fasta`, `fai`; Classy models and liftover assets within the locked Classy image |
| NASVAR | `nasvar.repeats`, `sites`, `gff`, `config`, `reference` |
| Clair3 | `models.clair3`: staged directory of model weights compatible with the basecaller chemistry/model |
| ClairS-TO | `models.clairsto`: platform/model identifier supported by the locked image |
| Stellerator | `callers.fusion_list`: Stellerator loci list; not the NASVAR target BED |
| Delly | `callers.delly_map`: mappability map built for the exact assembly |
| SubChrom | `callers.subchrom_panel`: prepared panel-bin BED matching the adaptive panel |
| ichorCNA | `callers.ichor_gc`, `ichor_map`, `ichor_centromeres`, `ichor_panel`, `ichor_seqinfo` |

The supplied NASVAR submodule has separate hg38 and CHM13 reference configurations. The workflow selects the matching pediatric leukemia configurations automatically; review their genes and thresholds against your panel.

Clair3 models are explicit paths rather than inferred from a `sup`/`hac` substring. ClairS-TO, Sniffles, Severus and Stellerator upstream images have additional internal model/annotation assets: verify these against your bundle during release validation. In particular, verify the CHM13 version of each tool's internal assets. Classy translates `hs1` to its `t2t` identifier and uses its own classifier liftover resources.

For broad copy-number callers, provide bins, GC/mappability resources and normal panels appropriate for the assay and chosen bin size (`--ichor_bin_size`, default 1 Mb; `--qdnaseq_binsize`, default 100 kb; `--delly_bin_size`, default 100 kb). These callers receive an off-target BAM; they must not be interpreted as a validated replacement for NASVAR without assay benchmarking. Preparing bins or model weights is a separate reference-preparation activity, not an implicit runtime download.

References, classifier weights, panels and basecaller models are not downloaded automatically. Pin their versions in the bundle ID, retain source/license information with the bundle, and keep immutable copies for reproducible analysis.
