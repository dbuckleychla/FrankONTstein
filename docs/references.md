# Reference bundles

Start from `assets/reference_bundle.example.json`. Set `schema_version: 1`, a versioned `id`, and `genome` (`hg38` or `hs1`). The selected `--genome`, if supplied, must agree with the bundle. CHM13 v1.1 and v2.0 are not interchangeable assets.

The bundle requires uncompressed FASTA and its FAI. Relative paths resolve against the bundle's location; absolute paths and S3 URLs are also accepted. Each run uses one bundle; run different builds separately. Input/index basenames must match (`reference.fa` / `reference.fa.fai`). The reference-validation process checks FASTA offsets and line widths against its FAI, then checks BED/GFF/site coordinates against contig lengths.

The target BED and enrichment BED are always CLI inputs, never inferred from each other or from a genome bundle. BED coordinates are zero-based half-open. GFF3 and NASVAR site coordinates are one-based. Headers in the sites TSV are not supported. Contig names must agree exactly; the workflow does not silently rename or lift over caller inputs.

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

The supplied NASVAR submodule has separate hg38 and CHM13 reference configurations. Select the matching configuration and review assay-specific gene/threshold settings. Do not reuse the pediatric leukemia example unchanged for unrelated assays.

Clair3 models are explicit paths rather than inferred from a `sup`/`hac` substring. ClairS-TO, Sniffles, Severus and Stellerator upstream images have additional internal model/annotation assets: verify these against your bundle during release validation. In particular, verify the CHM13 version of each tool's internal assets. Classy translates `hs1` to its `t2t` identifier and uses its own classifier liftover resources.

For broad copy-number callers, provide bins, GC/mappability resources and normal panels appropriate for the assay and chosen bin size (`--ichor_bin_size`, default 1 Mb; `--qdnaseq_binsize`, default 100 kb; `--delly_bin_size`, default 100 kb). These callers receive an off-target BAM; they must not be interpreted as a validated replacement for NASVAR without assay benchmarking. Preparing bins or model weights is a separate reference-preparation activity, not an implicit runtime download.

References, classifier weights, panels and basecaller models are not downloaded automatically. Pin their versions in the bundle ID, retain source/license information with the bundle, and keep immutable copies for reproducible analysis.
