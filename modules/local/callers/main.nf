/* Adapted from MIT-licensed chusj-pigu/wf-modules pinned by dependencies.json.
 * Explicit path inputs replace container-specific genome assets and panel paths.
 */
process OFF_TARGET_BAM {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(bam), path(bai)
    path assets
    output:
    tuple val(meta), path('offtarget.bam'), path('offtarget.bam.bai'), emit: bam
    script:
    """
    samtools view -b -L '${assets}/enrichment.bed' -U offtarget.bam -o /dev/null '${bam}'
    samtools index offtarget.bam
    """
    stub:
    """
    touch offtarget.bam offtarget.bam.bai
    """

}
process CLAIR3 {
    tag "${meta.id}"
    label 'high_memory'
    container { params.images.clair3 }
    input:
    tuple val(meta), path(bam), path(bai)
    tuple path(fasta), path(fai), val(validated)
    path assets
    output:
    tuple val(meta), path('clair3/merge_output.vcf.gz'), emit: vcf
    path 'versions.yml', emit: versions
    script:
    def model = WorkflowPlan.clair3Model(params.basecall_model)
    """
    test -s ${model}/pileup.pt || { echo 'Clair3 image is missing the bundled ${params.basecall_model} pileup model' >&2; exit 1; }
    test -s ${model}/full_alignment.pt || { echo 'Clair3 image is missing the bundled ${params.basecall_model} full-alignment model' >&2; exit 1; }
    run_clair3.sh --threads=${task.cpus} --sample_name='${meta.id}' \
      --platform=ont --model_path=${model} --bam_fn='${bam}' --ref_fn='${fasta}' \
      --bed_fn='${assets}/enrichment.bed' --output=clair3 ${params.clair3_gpu.toString().toBoolean() ? '--use_gpu' : ''}
    run_clair3.sh --version > versions.yml 2>&1
    """
    stub:
    """
    mkdir clair3
    touch clair3/merge_output.vcf.gz
    echo 'clair3: stub' > versions.yml
    """

}
process DELLY {
    tag "${meta.id}"
    container { params.images.delly }
    input:
    tuple val(meta), path(bam), path(bai)
    tuple path(fasta), path(fai), val(validated)
    path mappability
    output:
    tuple val(meta), path('delly.bcf'), emit: bcf
    tuple val(meta), path('delly.cov.gz'), emit: coverage
    path 'versions.yml', emit: versions
    script:
    """
    delly cnv -g '${fasta}' -m '${mappability}' -i ${params.delly_bin_size} \
      -w ${params.delly_bin_size} -c delly.cov.gz -o delly.bcf -s delly.stats.gz '${bam}'
    delly -v > versions.yml 2>&1
    """
    stub:
    """
    touch delly.bcf delly.cov.gz
    echo 'delly: stub' > versions.yml
    """

}
process SUBCHROM {
    tag "${meta.id}"
    container { params.images.subchrom }
    input:
    tuple val(meta), path(bam), path(bai), path(vcf)
    tuple path(fasta), path(fai), val(validated)
    path panel_bin
    output:
    tuple val(meta), path("${meta.id}.panel.SubChrom"), emit: results
    path 'versions.yml', emit: versions
    script:
    """
    mkdir -p '${meta.id}.panel.SubChrom'
    cp -L '${vcf}' '${meta.id}.panel.SubChrom/${meta.id}.panel.gatkHC.vcf.gz'
    SubChrom.sh -s '${meta.id}' -i '${bam}' -d panel -r '${fasta}' -p '${panel_bin}' -md hg38
    SubChrom.sh --help > versions.yml 2>&1
    """
    stub:
    """
    mkdir '${meta.id}.panel.SubChrom'
    touch '${meta.id}.panel.SubChrom/cnv.png'
    echo 'subchrom: stub' > versions.yml
    """

}
process ICHORCNA {
    tag "${meta.id}"
    container { params.images.ichorcna }
    input:
    tuple val(meta), path(wig)
    path gc_wig, stageAs:'ichor.gc.wig'
    path map_wig, stageAs:'ichor.map.wig'
    path centromeres, stageAs:'ichor.centromeres.txt'
    path normal_panel, stageAs:'ichor.panel.rds'
    path seqinfo, stageAs:'ichor.seqinfo.RData'
    output:
    tuple val(meta), path('ichorcna'), emit: results
    path 'versions.yml', emit: versions
    script:
    """
    mkdir ichorcna
    Rscript /opt/ichorCNA/scripts/runIchorCNA.R --id '${meta.id}' --WIG '${wig}' \
      --ploidy 'c(2,3)' --normal 'c(0.5,0.7,0.9)' --maxCN 5 \
      --gcWig '${gc_wig}' --mapWig '${map_wig}' --centromere '${centromeres}' \
      --normalPanel '${normal_panel}' --seqInfo '${seqinfo}' --genomeBuild hg38 \
      --genomeStyle UCSC --includeHOMD False --chrs 'c(1:22,"X")' --chrTrain 'c(1:22)' \
      --estimateNormal True --estimatePloidy True --estimateScPrevalence False \
      --txnE 0.9999 --txnStrength 10000 --outDir ichorcna
    printf 'ichorCNA: 0.2.0\n' > versions.yml
    """
    stub:
    """
    mkdir ichorcna
    touch ichorcna/cnv.pdf
    echo 'ichorcna: stub' > versions.yml
    """

}

process HMMCOPY_WIG {
    tag "${meta.id}"
    container { params.images.ichorcna }
    input:
    tuple val(meta), path(bam), path(bai), val(window), val(min_mapq)
    output:
    tuple val(meta), path('coverage.wig'), emit: wig
    path 'versions.yml', emit: versions
    script:
    """
    /opt/hmmcopy_utils/bin/readCounter --window ${window} --quality ${min_mapq} \
      -c chr1,chr2,chr3,chr4,chr5,chr6,chr7,chr8,chr9,chr10,chr11,chr12,chr13,chr14,chr15,chr16,chr17,chr18,chr19,chr20,chr21,chr22,chrX,chrY \
      '${bam}' > coverage.wig
    printf 'HMMcopy: 0.99.0\n' > versions.yml
    """
    stub:
    """
    touch coverage.wig
    echo 'hmmcopy: stub' > versions.yml
    """

}

process FILTER_VARIANTS {
    tag "${meta.id}:${caller}:${kind}"
    container { params.images.bcftools }
    input:
    tuple val(meta), val(caller), val(kind), path(vcf)
    path assets
    output:
    tuple val(meta), val(caller), path("${meta.id}.${kind}.targets.vcf.gz"), path("${meta.id}.${kind}.targets.vcf.gz.tbi"), emit: vcf
    path 'versions.yml', emit: versions
    script:
    """
    bcftools view -T '${assets}/targets.bed' -Oz -o '${meta.id}.${kind}.targets.vcf.gz' '${vcf}'
    bcftools index --tbi '${meta.id}.${kind}.targets.vcf.gz'
    bcftools --version > versions.yml
    """
    stub:
    """
    touch '${meta.id}.${kind}.targets.vcf.gz' '${meta.id}.${kind}.targets.vcf.gz.tbi'
    echo 'bcftools: stub' > versions.yml
    """
}
