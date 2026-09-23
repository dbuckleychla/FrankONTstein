include { FILTER_VARIANTS; CLAIR3; DELLY; SUBCHROM; ICHORCNA; HMMCOPY_WIG; OFF_TARGET_BAM } from '../../modules/local/callers/main'
include { BCFTOOLS_MPILEUP; BCFTOOLS_CALL } from '../../vendor/oncoseq/modules/local/bcftools/main'
include { CLAIRS_TO_CALL } from '../../vendor/oncoseq/modules/local/clairsto/main'
include { SNIFFLES_CALL } from '../../vendor/oncoseq/modules/local/sniffles/main'
include { SEVERUS_TUMOR_UNPHASED } from '../../vendor/oncoseq/modules/local/severus/main'
include { STELLERATOR } from '../../vendor/oncoseq/modules/local/stellerator/main'
include { QDNASEQ_CALL } from '../../vendor/oncoseq/modules/local/qdnaseq/main'

workflow CALLING {
    take:
    bam
    reference
    assets
    plan
    resources
    main:
    artifacts = Channel.empty()
    versions = Channel.empty()
    smallVariants = Channel.empty()
    if (plan.callers.contains('bcftools')) {
        BCFTOOLS_MPILEUP(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,f,fi) })
        BCFTOOLS_CALL(BCFTOOLS_MPILEUP.out.bcf)
        smallVariants = smallVariants.mix(BCFTOOLS_CALL.out.vcf.map { m,f -> tuple(m,'bcftools','variants',f) })
        artifacts = artifacts.mix(BCFTOOLS_CALL.out.vcf.map { m,f -> tuple(m,'bcftools',f) })
        versions = versions.mix(BCFTOOLS_MPILEUP.out.versions, BCFTOOLS_CALL.out.versions)
    }
    if (plan.callers.contains('clair3')) {
        CLAIR3(bam, reference, assets)
        smallVariants = smallVariants.mix(CLAIR3.out.vcf.map { m,f -> tuple(m,'clair3','variants',f) })
        artifacts = artifacts.mix(CLAIR3.out.vcf.map { m,f -> tuple(m,'clair3',f) })
        versions = versions.mix(CLAIR3.out.versions)
    }
    if (plan.callers.contains('clairsto')) {
        CLAIRS_TO_CALL(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,f,fi,resources.clairsto_model) })
        artifacts = artifacts.mix(CLAIRS_TO_CALL.out.snv.map { m,f -> tuple(m,'clairsto',f) }, CLAIRS_TO_CALL.out.indel.map { m,f -> tuple(m,'clairsto',f) })
        versions = versions.mix(CLAIRS_TO_CALL.out.versions)
        smallVariants = smallVariants.mix(CLAIRS_TO_CALL.out.snv.map { m,f -> tuple(m,'clairsto','snv',f) }, CLAIRS_TO_CALL.out.indel.map { m,f -> tuple(m,'clairsto','indel',f) })
    }
    if (plan.callers.contains('sniffles')) {
        SNIFFLES_CALL(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,plan.genome,f,fi) })
        artifacts = artifacts.mix(SNIFFLES_CALL.out.vcf.map { m,f -> tuple(m,'sniffles',f) })
        versions = versions.mix(SNIFFLES_CALL.out.versions)
    }
    if (plan.callers.contains('severus')) {
        SEVERUS_TUMOR_UNPHASED(bam.map { m,b,i -> tuple(m,b,i,plan.genome) })
        artifacts = artifacts.mix(SEVERUS_TUMOR_UNPHASED.out.vcf.map { m,f -> tuple(m,'severus',f) })
        versions = versions.mix(SEVERUS_TUMOR_UNPHASED.out.versions)
    }
    if (plan.callers.contains('stellerator')) {
        STELLERATOR(bam.map { m,b,i -> tuple(m,b,i,plan.genome,resources.fusion_list) })
        artifacts = artifacts.mix(STELLERATOR.out.vcf.map { m,f -> tuple(m,'stellerator',f) }, STELLERATOR.out.tsv.map { m,f -> tuple(m,'stellerator',f) }, STELLERATOR.out.fasta.map { m,f -> tuple(m,'stellerator',f) })
        versions = versions.mix(STELLERATOR.out.versions)
    }
    if (plan.callers.intersect(['qdnaseq','delly','ichorcna'])) {
        OFF_TARGET_BAM(bam, assets)
    }
    if (plan.callers.contains('qdnaseq')) {
        QDNASEQ_CALL(OFF_TARGET_BAM.out.bam.map { m,b,i -> tuple(m,b,i,plan.genome) })
        artifacts = artifacts.mix(QDNASEQ_CALL.out.calls_bed.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.cov_png.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.call_vcf.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_vcf.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_bed.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_seg.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.noise_png.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.isobar_png.map { m,f -> tuple(m,'qdnaseq',f) })
        versions = versions.mix(QDNASEQ_CALL.out.versions)
    }
    if (plan.callers.contains('delly')) {
        DELLY(OFF_TARGET_BAM.out.bam, reference, resources.delly_map)
        artifacts = artifacts.mix(DELLY.out.bcf.map { m,f -> tuple(m,'delly',f) }, DELLY.out.coverage.map { m,f -> tuple(m,'delly',f) })
        versions = versions.mix(DELLY.out.versions)
    }
    if (plan.callers.contains('subchrom')) {
        SUBCHROM(bam.join(CLAIR3.out.vcf), reference, resources.subchrom_panel)
        artifacts = artifacts.mix(SUBCHROM.out.results.map { m,f -> tuple(m,'subchrom',f) })
        versions = versions.mix(SUBCHROM.out.versions)
    }
    if (plan.callers.contains('ichorcna')) {
        HMMCOPY_WIG(OFF_TARGET_BAM.out.bam.map { m,b,i -> tuple(m,b,i,params.ichor_bin_size,20) })
        ICHORCNA(HMMCOPY_WIG.out.wig, resources.ichor_gc, resources.ichor_map, resources.ichor_centromeres, resources.ichor_panel, resources.ichor_seqinfo)
        artifacts = artifacts.mix(ICHORCNA.out.results.map { m,f -> tuple(m,'ichorcna',f) })
        versions = versions.mix(HMMCOPY_WIG.out.versions, ICHORCNA.out.versions)
    }
    if (plan.callers.intersect(['bcftools','clair3','clairsto'])) {
        FILTER_VARIANTS(smallVariants, assets)
        artifacts = artifacts.mix(FILTER_VARIANTS.out.vcf.map { m,caller,vcf,index -> tuple(m,caller,[vcf,index]) })
        versions = versions.mix(FILTER_VARIANTS.out.versions)
    }
    emit:
    results = artifacts
    software = versions
}
