process MODKIT_PILEUP {
    tag "${meta.id}"
    container { params.images.classy }
    input:
    tuple val(meta), path(bam), path(bai)
    tuple path(fasta), path(fai), val(validated)
    output:
    tuple val(meta), path("${meta.id}.cpg.bedmethyl.gz"), emit: bed
    tuple val(meta), path("${meta.id}.modkit.log"), emit: log
    path 'modkit.versions.yml', emit: versions
    script:
    """
    modkit pileup '${bam}' '${meta.id}.cpg.bedmethyl.gz' --ref '${fasta}' \
      --cpg --combine-strands --bgzf --threads ${task.cpus} \
      --log-filepath '${meta.id}.modkit.log'
    modkit --version > modkit.versions.yml
    """
    stub:
    """
    printf '' | gzip > '${meta.id}.cpg.bedmethyl.gz'
    echo 'stub' > '${meta.id}.modkit.log'
    echo 'modkit: stub' > modkit.versions.yml
    """
}

process INDEX_BEDMETHYL {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(bed)
    output:
    tuple val(meta), path("${bed}"), path("${bed}.tbi"), emit: bed
    script:
    """
    python3 -c "import pysam; pysam.tabix_index('${bed}', preset='bed', force=True)"
    """
    stub:
    """
    touch '${bed}.tbi'
    """
}

process SAMPLE_QC {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(bam), path(bai), path(bed), path(tbi), path(preprocessing, stageAs:'preprocessing/??/*')
    tuple path(fasta), path(fai), val(validated)
    path enrichment, stageAs:'enrichment.bed'
    path targets, stageAs:'targets.bed'
    output:
    tuple val(meta), path('qc'), emit: results
    path 'qc/metrics.json', emit: metrics
    path 'qc.versions.yml', emit: versions
    script:
    """
    adaptive_qc.py --sample '${meta.id}' --bam '${bam}' --fasta '${fasta}' \
      --bedmethyl '${bed}' --enrichment '${enrichment}' --targets '${targets}' \
      --threads ${task.cpus} --input-run '${meta.input_run ?: meta.id}' --input-scope ${meta.input_run ? 'run' : 'sample'} --preprocessing preprocessing/*/*
    samtools --version | head -1 > qc.versions.yml
    python3 -c 'import pysam; print("pysam: " + pysam.__version__)' >> qc.versions.yml
    """
    stub:
    """
    mkdir qc
    echo '{"sample":"${meta.id}","stub":true}' > qc/metrics.json
    echo '<html>QC stub</html>' > qc/index.html
    touch qc/summary.tsv qc/targets.tsv
    echo 'qc: stub' > qc.versions.yml
    """
}

process DEMUX_QC {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(bams, stageAs:'barcodes/*')
    output:
    tuple val(meta), path('demux_qc.json'), emit: qc
    script:
    """
    demux_qc.py --threads ${task.cpus} --run '${meta.id}' barcodes/* > demux_qc.json
    """
    stub:
    """
    echo '{"run":"${meta.id}","stub":true}' > demux_qc.json
    """
}
