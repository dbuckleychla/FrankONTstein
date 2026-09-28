process PREPARE_BAM {
    tag "${meta.id}"
    label 'high_memory'
    container { params.images.preprocess }
    publishDir { "${params.outdir}/${meta.id}/preprocessing" }, mode: 'copy', pattern: '*.json', saveAs: { name -> name.contains(meta.id) ? name : "${meta.id}.${name}" }
    input:
    tuple val(meta), path(bams, stageAs: 'chunks/input??.bam')
    output:
    tuple val(meta), path('prepared.bam'), emit: bam
    tuple val(meta), path('input_qc.json'), emit: qc
    path 'prepare.versions.yml', emit: versions
    script:
    def chunks = bams instanceof List ? bams : [bams]
    """
    cat_bam_header.py --provenance cat_header.json ${chunks.collect { "'${it}'" }.join(' ')} > cat.header.sam
    ${chunks.size() == 1 ? "ln -s '${chunks[0]}' prepared.bam" : "samtools cat -h cat.header.sam -o prepared.bam " + chunks.collect { "'${it}'" }.join(' ')}
    check_bam.py prepared.bam --unaligned --max-reads 1000 ${Basecalling.enabled(params as Map) ? '--require-cpg-modifications' : ''} ${meta.require_moves ? '--require-moves' : ''} > input_qc.json
    python3 - <<'PYQC'
    import json
    from pathlib import Path
    p = Path('input_qc.json')
    data = json.loads(p.read_text())
    data['processing_stage'] = '${WorkflowPlan.adapterTrimming(params as Map) ? 'prepared_after_adapter_trimming' : 'prepared_without_adapter_trimming'}'
    p.write_text(json.dumps(data))
    PYQC
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
    tag "${meta.id}:${shard_id}"
    container { params.images.preprocess }
    publishDir { "${params.outdir}/demultiplex/${meta.id}/${shard_id}" }, mode: 'copy', pattern: 'demux/**', saveAs: { name -> name.replaceFirst('demux/', '') }
    input:
    tuple val(meta), val(shard_id), path(bam)
    output:
    tuple val(meta), val(shard_id), path('demux/**.bam'), emit: bams
    path 'demux.versions.yml', emit: versions
    script:
    """
    dorado demux --threads ${task.cpus} --kit-name '${meta.kit}' --output-dir demux '${bam}'
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
    tag "${meta.id}:${shard_id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), val(shard_id), path(bam)
    output:
    tuple val(meta), val(shard_id), path('trimmed.bam'), emit: bam
    path 'trim.versions.yml', emit: versions
    script:
    if (!meta.kit) error 'Dorado trimming requires a sequencing kit in sample metadata'
    WorkflowPlan.identifier(meta.kit.toString())
    """
    dorado trim --sequencing-kit '${meta.kit}' '${bam}' > trimmed.bam
    dorado --version > trim.versions.yml 2>&1
    """
    stub:
    """
    touch trimmed.bam
    echo 'dorado: stub' > trim.versions.yml
    """

}

process ALIGN {
    tag "${meta.id}"
    label 'high_memory'
    container { params.images.preprocess }
    publishDir { "${params.outdir}/${meta.id}/alignment" }, mode: 'copy', saveAs: { name -> name.contains(meta.id) ? name : "${meta.id}.${name}" }
    input:
    tuple val(meta), path(bam)
    tuple path(fasta, stageAs:'reference.fa'), path(fai, stageAs:'reference.fa.fai'), val(validated)
    output:
    tuple val(meta), path("${meta.id}.bam"), path("${meta.id}.bam.bai"), emit: bam
    tuple val(meta), path("${meta.id}.qc.json"), emit: qc
    path "${meta.id}.idxstats.txt", emit: idxstats
    path 'alignment.versions.yml', emit: versions
    script:
    """
    dorado aligner --threads ${Math.max(1, (task.cpus as int) - Math.max(1, (task.cpus as int).intdiv(4)))} reference.fa '${bam}' |
        samtools sort -@ ${Math.max(1, (task.cpus as int).intdiv(4))} -m 1G -o sorted.bam -
    bam_sample_header.py sorted.bam '${meta.id}' > sample.header.sam
    samtools reheader sample.header.sam sorted.bam > '${meta.id}.bam'
    rm sorted.bam
    samtools index '${meta.id}.bam'
    check_bam.py '${meta.id}.bam' --max-reads 1000 ${Basecalling.enabled(params as Map) ? '--require-cpg-modifications' : ''} ${meta.require_moves ? '--require-moves' : ''} > '${meta.id}.qc.json'
    samtools idxstats '${meta.id}.bam' > '${meta.id}.idxstats.txt'
    dorado --version > alignment.versions.yml 2>&1
    """
    stub:
    """
    touch '${meta.id}.bam' '${meta.id}.bam.bai'
    touch '${meta.id}.idxstats.txt'
    echo '{"stub":true}' > '${meta.id}.qc.json'
    echo 'dorado: stub' > alignment.versions.yml
    """

}
