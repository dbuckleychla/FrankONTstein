include { SOMATIC_CONSENSUS } from '../../modules/local/consensus/main'
include { FINALIZE_VARIANTS } from '../../modules/local/finalize_variants/main'
include { FILTER_VARIANTS; CLAIR3; DELLY; SUBCHROM; ICHORCNA; HMMCOPY_WIG; OFF_TARGET_BAM } from '../../modules/local/callers/main'
include { BCFTOOLS_MPILEUP } from '../../modules/local/bcftools/main'
include { BCFTOOLS_CALL } from '../../modules/local/oncoseq_logged/main'
include { DEEPSOMATIC } from '../../modules/local/deepsomatic/main'
include { CLAIRS_TO_CALL } from '../../modules/local/clairsto/main'
include { SNIFFLES_CALL } from '../../modules/local/oncoseq_logged/main'
include { SEVERUS_TUMOR_UNPHASED } from '../../modules/local/oncoseq_logged/main'
include { STELLERATOR } from '../../modules/local/oncoseq_logged/main'
include { QDNASEQ_CALL } from '../../modules/local/oncoseq_logged/main'

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
    otherVariants = Channel.empty()
    if (plan.callers.contains('bcftools')) {
        BCFTOOLS_MPILEUP(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,f,fi) }, assets)
        artifacts = artifacts.mix(BCFTOOLS_MPILEUP.out.logs.map { m,f -> tuple(m,'bcftools',f) })
        BCFTOOLS_CALL(BCFTOOLS_MPILEUP.out.bcf)
        artifacts = artifacts.mix(BCFTOOLS_CALL.out.logs.map { m,f -> tuple(m,'bcftools',f) })
        smallVariants = smallVariants.mix(BCFTOOLS_CALL.out.vcf.map { m,f -> tuple(m,'bcftools','variants',f) })
        artifacts = artifacts.mix(BCFTOOLS_CALL.out.vcf.map { m,f -> tuple(m,'bcftools',f) })
        versions = versions.mix(BCFTOOLS_MPILEUP.out.versions, BCFTOOLS_CALL.out.versions)
    }
    if (plan.callers.contains('deepsomatic')) {
        DEEPSOMATIC(bam, reference, assets)
        artifacts = artifacts.mix(DEEPSOMATIC.out.results.map { m,files -> tuple(m,'deepsomatic',files) })
        smallVariants = smallVariants.mix(DEEPSOMATIC.out.vcf.map { m,f -> tuple(m,'deepsomatic','variants',f) })
        versions = versions.mix(DEEPSOMATIC.out.versions)
    }
    if (plan.callers.contains('clair3')) {
        CLAIR3(bam, reference, assets, resources.clair3_model ?: [])
        artifacts = artifacts.mix(CLAIR3.out.logs.map { m,f -> tuple(m,'clair3',f) })
        smallVariants = smallVariants.mix(CLAIR3.out.vcf.map { m,f -> tuple(m,'clair3','variants',f) })
        artifacts = artifacts.mix(CLAIR3.out.vcf.map { m,f -> tuple(m,'clair3',f) })
        versions = versions.mix(CLAIR3.out.versions)
    }
    if (plan.callers.contains('clairsto')) {
        CLAIRS_TO_CALL(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,f,fi,resources.clairsto_model) })
        artifacts = artifacts.mix(CLAIRS_TO_CALL.out.logs.map { m,f -> tuple(m,'clairsto',f) })
        artifacts = artifacts.mix(CLAIRS_TO_CALL.out.snv.map { m,f -> tuple(m,'clairsto',f) }, CLAIRS_TO_CALL.out.indel.map { m,f -> tuple(m,'clairsto',f) })
        versions = versions.mix(CLAIRS_TO_CALL.out.versions)
        smallVariants = smallVariants.mix(CLAIRS_TO_CALL.out.snv.map { m,f -> tuple(m,'clairsto','snv',f) }, CLAIRS_TO_CALL.out.indel.map { m,f -> tuple(m,'clairsto','indel',f) })
    }
    if (plan.callers.contains('sniffles')) {
        SNIFFLES_CALL(bam.combine(reference).map { m,b,i,f,fi,v -> tuple(m,b,i,plan.genome,f,fi) })
        artifacts = artifacts.mix(SNIFFLES_CALL.out.logs.map { m,f -> tuple(m,'sniffles',f) })
        artifacts = artifacts.mix(SNIFFLES_CALL.out.vcf.map { m,f -> tuple(m,'sniffles',f) })
        otherVariants = otherVariants.mix(SNIFFLES_CALL.out.vcf.map { m,f -> tuple(m,'sniffles','sv',f) })
        versions = versions.mix(SNIFFLES_CALL.out.versions)
    }
    if (plan.callers.contains('severus')) {
        SEVERUS_TUMOR_UNPHASED(bam.map { m,b,i -> tuple(m,b,i,plan.genome) })
        artifacts = artifacts.mix(SEVERUS_TUMOR_UNPHASED.out.logs.map { m,f -> tuple(m,'severus',f) })
        artifacts = artifacts.mix(SEVERUS_TUMOR_UNPHASED.out.vcf.map { m,f -> tuple(m,'severus',f) })
        otherVariants = otherVariants.mix(SEVERUS_TUMOR_UNPHASED.out.vcf.map { m,f -> tuple(m,'severus','sv',f) })
        versions = versions.mix(SEVERUS_TUMOR_UNPHASED.out.versions)
    }
    if (plan.callers.contains('stellerator')) {
        STELLERATOR(bam.map { m,b,i -> tuple(m,b,i,plan.genome,resources.fusion_list) })
        artifacts = artifacts.mix(STELLERATOR.out.logs.map { m,f -> tuple(m,'stellerator',f) })
        artifacts = artifacts.mix(STELLERATOR.out.vcf.map { m,f -> tuple(m,'stellerator',f) }, STELLERATOR.out.tsv.map { m,f -> tuple(m,'stellerator',f) }, STELLERATOR.out.fasta.map { m,f -> tuple(m,'stellerator',f) })
        otherVariants = otherVariants.mix(STELLERATOR.out.vcf.map { m,f -> tuple(m,'stellerator','fusions',f) })
        versions = versions.mix(STELLERATOR.out.versions)
    }
    if (plan.callers.intersect(['qdnaseq','delly','ichorcna'])) {
        OFF_TARGET_BAM(bam, assets)
        artifacts = artifacts.mix(OFF_TARGET_BAM.out.logs.map { m,f -> tuple(m,'alignment',f) })
    }
    if (plan.callers.contains('qdnaseq')) {
        QDNASEQ_CALL(OFF_TARGET_BAM.out.bam.map { m,b,i -> tuple(m,b,i,plan.genome) })
        artifacts = artifacts.mix(QDNASEQ_CALL.out.logs.map { m,f -> tuple(m,'qdnaseq',f) })
        artifacts = artifacts.mix(QDNASEQ_CALL.out.calls_bed.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.cov_png.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.call_vcf.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_vcf.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_bed.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.segs_seg.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.noise_png.map { m,f -> tuple(m,'qdnaseq',f) }, QDNASEQ_CALL.out.isobar_png.map { m,f -> tuple(m,'qdnaseq',f) })
        otherVariants = otherVariants.mix(QDNASEQ_CALL.out.call_vcf.map { m,f -> tuple(m,'qdnaseq','calls',f) })
        otherVariants = otherVariants.mix(QDNASEQ_CALL.out.segs_vcf.map { m,f -> tuple(m,'qdnaseq','segments',f) })
        versions = versions.mix(QDNASEQ_CALL.out.versions)
    }
    if (plan.callers.contains('delly')) {
        DELLY(OFF_TARGET_BAM.out.bam, reference, resources.delly_map)
        artifacts = artifacts.mix(DELLY.out.logs.map { m,f -> tuple(m,'delly',f) })
        artifacts = artifacts.mix(DELLY.out.bcf.map { m,f -> tuple(m,'delly',f) }, DELLY.out.coverage.map { m,f -> tuple(m,'delly',f) })
        otherVariants = otherVariants.mix(DELLY.out.bcf.map { m,f -> tuple(m,'delly','cnv',f) })
        versions = versions.mix(DELLY.out.versions)
    }
    if (plan.callers.contains('subchrom')) {
        SUBCHROM(bam.join(CLAIR3.out.vcf), reference, resources.subchrom_panel)
        artifacts = artifacts.mix(SUBCHROM.out.logs.map { m,f -> tuple(m,'subchrom',f) })
        artifacts = artifacts.mix(SUBCHROM.out.results.map { m,f -> tuple(m,'subchrom',f) })
        versions = versions.mix(SUBCHROM.out.versions)
    }
    if (plan.callers.contains('ichorcna')) {
        HMMCOPY_WIG(OFF_TARGET_BAM.out.bam.map { m,b,i -> tuple(m,b,i,params.ichor_bin_size,20) })
        artifacts = artifacts.mix(HMMCOPY_WIG.out.logs.map { m,f -> tuple(m,'ichorcna',f) })
        ICHORCNA(HMMCOPY_WIG.out.wig, resources.ichor_gc, resources.ichor_map, resources.ichor_centromeres, resources.ichor_panel, resources.ichor_seqinfo)
        artifacts = artifacts.mix(ICHORCNA.out.logs.map { m,f -> tuple(m,'ichorcna',f) })
        artifacts = artifacts.mix(ICHORCNA.out.results.map { m,f -> tuple(m,'ichorcna',f) })
        versions = versions.mix(HMMCOPY_WIG.out.versions, ICHORCNA.out.versions)
    }
    finalizedInputs = otherVariants.mix(smallVariants.map { m,c,k,f -> tuple(m,c,k+'.raw',f) })
    if (plan.callers.intersect(['bcftools','clair3','clairsto','deepsomatic'])) {
        FILTER_VARIANTS(smallVariants, assets)
        artifacts = artifacts.mix(FILTER_VARIANTS.out.vcf.map { m,caller,vcf,index -> tuple(m,caller,[vcf,index]) })
        versions = versions.mix(FILTER_VARIANTS.out.versions)
        finalizedInputs = finalizedInputs.mix(FILTER_VARIANTS.out.vcf.map { m,c,f,i -> tuple(m,c,f.name.substring(m.id.size()+1).replace('.vcf.gz',''),f) })
    }
    if (plan.callers.containsAll(['deepsomatic','clairsto'])) {
        consensusInputs = FILTER_VARIANTS.out.vcf
            .filter { m,c,f,i -> c in ['deepsomatic','clairsto'] }
            .map { m,c,f,i -> tuple(m, [caller:c, file:f]) }
            .groupTuple()
            .map { m, rows ->
                def ds = rows.findAll { it.caller == 'deepsomatic' }.collect { it.file }.sort { it.name }
                def cs = rows.findAll { it.caller == 'clairsto' }.collect { it.file }.sort { it.name }
                if (ds.size() != 1 || cs.size() != 2) error "Incomplete somatic caller inputs for ${m.id}"
                tuple(m, ds, cs)
            }
        SOMATIC_CONSENSUS(consensusInputs, reference, assets)
        artifacts = artifacts.mix(SOMATIC_CONSENSUS.out.results.map { m,f -> tuple(m,'consensus',f) })
        versions = versions.mix(SOMATIC_CONSENSUS.out.versions)
    }
    FINALIZE_VARIANTS(finalizedInputs, reference.map { f,fi,v -> fi })
    artifacts = artifacts.mix(FINALIZE_VARIANTS.out.results)
    versions = versions.mix(FINALIZE_VARIANTS.out.versions)
    emit:
    results = artifacts
    software = versions
}
