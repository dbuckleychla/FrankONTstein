process PREPARE_BAM {
    tag "${meta.id}"
    label 'high_memory'
    container { params.images.preprocess }
    publishDir { "${params.outdir}/${meta.id}/preprocessing" }, mode: 'copy', pattern: '*.json'
    input:
    tuple val(meta), path(bams, stageAs: 'chunks/input??.bam')
    output:
    tuple val(meta), path('prepared.bam'), emit: bam
    tuple val(meta), path('input_qc.json'), emit: qc
    path 'prepare.versions.yml', emit: versions
    script:
    def chunks = bams instanceof List ? bams : [bams]
    """
    samtools merge -u -@ ${task.cpus} prepared.bam ${chunks.collect { "'${it}'" }.join(' ')}
    check_bam.py prepared.bam --unaligned --threads ${task.cpus} ${Basecalling.enabled(params as Map) ? '--require-cpg-modifications' : ''} ${meta.require_moves ? '--require-moves' : ''} > input_qc.json
    samtools --version | sed -n '1p' > prepare.versions.yml
    """
    stub:
    """
    touch prepared.bam
    echo '{"stub":true}' > input_qc.json
    echo 'samtools: stub' > prepare.versions.yml
    """

}

process DEMULTIPLEX {
    tag "${meta.id}"
    container { params.images.preprocess }
    publishDir { "${params.outdir}/demultiplex/${meta.id}" }, mode: 'copy', pattern: 'demux/**', saveAs: { name -> name.replaceFirst('demux/', '') }
    input:
    tuple val(meta), path(bam)
    output:
    tuple val(meta), path('demux/**.bam'), emit: bams
    path 'demux.versions.yml', emit: versions
    script:
    """
    dorado demux --kit-name '${meta.kit}' --no-trim --output-dir demux '${bam}'
    find demux -type f -print
    dorado --version > demux.versions.yml 2>&1
    """
    stub:
    def names = meta.mappings.collect { "mkdir -p demux/${it.barcode}; touch demux/${it.barcode}/${it.barcode}.bam" }.join('\n')
    """
    mkdir demux
    ${names}
    touch demux/unclassified.bam
    echo 'dorado: stub' > demux.versions.yml
    """

}

process TRIM_BAM {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(bam)
    output:
    tuple val(meta), path('trimmed.bam'), emit: bam
    tuple val(meta), path('trim_qc.json'), emit: qc
    path 'trim.versions.yml', emit: versions
    script:
    if (!meta.kit) error 'Dorado trimming requires a sequencing kit in sample metadata'
    WorkflowPlan.identifier(meta.kit.toString())
    """
    dorado trim --sequencing-kit '${meta.kit}' '${bam}' > trimmed.bam
    check_bam.py trimmed.bam --unaligned --threads ${task.cpus} ${Basecalling.enabled(params as Map) ? '--require-cpg-modifications' : ''} ${meta.require_moves ? '--require-moves' : ''} > trim_qc.json
    dorado --version > trim.versions.yml 2>&1
    """
    stub:
    """
    touch trimmed.bam
    echo '{"stub":true}' > trim_qc.json
    echo 'dorado: stub' > trim.versions.yml
    """

}

process ALIGN {
    tag "${meta.id}"
    label 'high_memory'
    container { params.images.preprocess }
    publishDir { "${params.outdir}/${meta.id}/alignment" }, mode: 'copy'
    input:
    tuple val(meta), path(bam)
    tuple path(fasta, stageAs:'reference.fa'), path(fai, stageAs:'reference.fa.fai'), val(validated)
    output:
    tuple val(meta), path("${meta.id}.bam"), path("${meta.id}.bam.bai"), emit: bam
    tuple val(meta), path("${meta.id}.qc.json"), emit: qc
    path "${meta.id}.flagstat.txt", emit: flagstat
    path 'alignment.versions.yml', emit: versions
    script:
    """
    dorado aligner --threads ${task.cpus} reference.fa '${bam}' |
        samtools sort -@ ${task.cpus} -o '${meta.id}.bam' -
    samtools index '${meta.id}.bam'
    check_bam.py '${meta.id}.bam' --threads ${task.cpus} ${Basecalling.enabled(params as Map) ? '--require-cpg-modifications' : ''} ${meta.require_moves ? '--require-moves' : ''} > '${meta.id}.qc.json'
    samtools flagstat '${meta.id}.bam' > '${meta.id}.flagstat.txt'
    dorado --version > alignment.versions.yml 2>&1
    """
    stub:
    """
    touch '${meta.id}.bam' '${meta.id}.bam.bai'
    touch '${meta.id}.flagstat.txt'
    echo '{"stub":true}' > '${meta.id}.qc.json'
    echo 'dorado: stub' > alignment.versions.yml
    """

}
