# Public sources for the reference configuration

Inventory checked against the pinned source checkouts on 2026-09-22. Live HTTP
availability could not be verified in this environment (DNS unavailable). These
are source locations, not an assurance of compatibility with every FASTA.
Preserve download versions/checksums. Do not mix UCSC hg38, Ensembl primary
assembly, or CHM13 versions merely because their build aliases look equivalent.

| Configuration field | Public source or preparation needed |
| --- | --- |
| `reference_id` | User-defined provenance label; no download. |
| `fasta` | UCSC [hg38 FASTA](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz) or [hs1 FASTA](https://hgdownload.soe.ucsc.edu/goldenPath/hs1/bigZips/hs1.fa.gz). Decompress and run `samtools faidx`. Confirm the precise assembly and contig set against all other assets. |
| `targets_bed` | Custom pediatric-leukemia target panel; no universal replacement. |
| `enrichment_bed` | The actual BED used for adaptive sampling; custom experiment design. |
| `image_manifest` | `images.lock.json` downloaded from the container-build Actions artifact; not a genomic reference. |
| `steps.nasvar.repeats` | Public RepeatMasker annotations: [hg38 rmsk table](https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/rmsk.txt.gz), [hs1 table directory](https://hgdownload.soe.ucsc.edu/goldenPath/hs1/database/). The rmsk SQL table is **not BED**; extract chromosome/start/end columns according to its schema, sort/merge as appropriate, and validate against the FASTA. |
| `steps.nasvar.sites` | A prepared common-SNP list. Public candidate sources include [1000 Genomes GRCh38](https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000_genomes_project/release/20181203_biallelic_SNV/) and [dbSNP VCF releases](https://ftp.ncbi.nih.gov/snp/latest_release/VCF/). Select suitable biallelic SNPs and convert to NASVAR's headerless `chromosome, position, REF, ALT` TSV (one-based position). Not a VCF path. No ready-made compatible CHM13 NASVAR site list was identified in the pinned source; obtain or prepare a validated build-specific list. |
| `steps.nasvar.gff` | Public [GENCODE human releases](https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/) or [NCBI Datasets genome annotations](https://www.ncbi.nlm.nih.gov/datasets/genome/). NASVAR expects GFF3, including gene `Name` and ID/Parent relationships; a GTF is not interchangeable. Choose the exact assembly, check gene attributes, and normalize accession-vs-chr names only using a verified assembly mapping. |
| Clair3 | Bundled models selected by `basecall_model: sup` (default), `hac` or `fast`. SUP uses SUP v5.0; HAC/FAST use HAC v5.0. No separate model download. |
| `steps.clairsto.model` | Model identifier, not a downloaded path. See [ClairS-TO](https://github.com/HKU-BAL/ClairS-TO) and verify availability in the locked image. Match chemistry/basecalling, not genome alone. |
| `steps.stellerator.fusion_list` | Custom fusion loci for your pediatric-leukemia panel in Stellerator `--loci` format; the annotation GTF is already in its image. Do not substitute a generic gene list or GTF for this file. |
| `steps.delly.map` | Public [Delly mappability resources](https://gear-genomics.embl.de/data/delly/). See exact upstream links and the compatibility notes below. |
| `steps.subchrom.panel` | Custom panel-bin BED for your enrichment design. Public [SubChrom resources](https://zenodo.org/records/10155688) contain SNP markers; those are **not** a replacement for this panel file. |
| `steps.ichorcna.gc` | Public hg38 GC WIG; already in the pinned module (see below). Bin size must match `--ichor_bin_size`. |
| `steps.ichorcna.map` | Public hg38 mappability WIG; already in the pinned module. Same bin-size requirement. |
| `steps.ichorcna.centromeres` | Public hg38 centromere table; already in the pinned module. |
| `steps.ichorcna.panel` | Standard public hg38 low-pass-WGS normal panel; selected in the example when no adaptive-sampling panel is available. |
| `steps.ichorcna.seqinfo` | Generated R object containing chromosome lengths/styles; generate once with the locked ichorCNA environment. See below. |

NASVAR's hg38/CHM13 reference and pediatric leukemia config JSONs are already
selected from `vendor/nasvar/config`; no additional download is required.

## ichorCNA hg38 files: already available locally

The reference example uses the standard public hg38 files, including the normal
panel, as requested when no adaptive-sampling panel is available. This does not
change their provenance or establish assay validation. The current workflow
default is 1 Mb bins. These files exist under
`vendor/oncoseq/modules/local/ichorcna/ichorCNA/inst/extdata/` after normal bootstrap:

| Field | File |
| --- | --- |
| `gc` | `gc_hg38_1000kb.wig` |
| `map` | `map_hg38_1000kb.wig` |
| `centromeres` | `GRCh38.GCA_000001405.2_centromere_acen.txt` |
| `panel` | `HD_ULP_PoN_hg38_1Mb_median_normAutosome_median.rds` |

Public copies matching the pinned module are downloadable from this immutable
source directory (append the filename above):

```text
https://raw.githubusercontent.com/chusj-pigu/wf-modules/178a93cc171e7ad92248755099aa43083e5eb7d0/ichorCNA/inst/extdata/
```

For example:

```bash
curl -fL -o gc_hg38_1000kb.wig \
  https://raw.githubusercontent.com/chusj-pigu/wf-modules/178a93cc171e7ad92248755099aa43083e5eb7d0/ichorCNA/inst/extdata/gc_hg38_1000kb.wig
```

The upstream [ichorCNA extdata directory](https://github.com/broadinstitute/ichorCNA/tree/master/inst/extdata)
also carries public resources. The pinned module includes 10/50/500/1000 kb GC
and mappability files for hg38, and 500 kb/1 Mb public normal panels. Keep all
binning consistent. These assets do not enable CHM13 support: ichorCNA remains
excluded for CHM13 in this workflow.

`seqinfo.RData` is generated, not an identified static download. In the locked
ichorCNA R environment, generate a UCSC-style hg38 object once using
`GenomeInfoDb::Seqinfo(genome="hg38")`, retain the chromosomes used by the
workflow (chr1–chr22, chrX, chrY), and save an object **named `seqinfo`** with
`save(seqinfo, file="seqinfo.RData")`. This metadata lookup needs internet unless
an appropriate BSgenome package is available. Compare its lengths with your FAI
before use. The pinned module also offers `runIchorCNA.R --downloadOnly True
--genomeBuild hg38 --genomeStyle UCSC` with its other required arguments.

## Delly maps need exact assembly matching

The pinned upstream Dockerfile references these public maps:

- [GRCh38 primary assembly map](https://gear-genomics.embl.de/data/delly/Homo_sapiens.GRCh38.dna.primary_assembly.fa.r101.s501.blacklist.gz)
- [CHM13 **v1.1** map](https://gear-genomics.embl.de/data/delly/T2T-CHM13v1.1.fa.r101.s501.gz)

The latter is **not** a CHM13v2.0/hs1 map. The former is not automatically
compatible with UCSC hg38 contig names or its complete contig set. Use a matching
reference/map pair or generate a map for the exact FASTA using Delly's documented
procedure. The `.gz` map is a specialized map file, not a generic BED or the
ichorCNA mappability WIG. Upstream also supplies `.fai` and `.gzi` sidecars; retain
them with downloaded maps and verify the caller's staging/index requirements
before a real Delly run.
