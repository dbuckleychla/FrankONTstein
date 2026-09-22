process NASVAR {
    tag "${meta.id}:${tier}"
    label 'high_memory'
    container { params.images.nasvar }
    publishDir { "${params.outdir}/${meta.id}/variants" }, mode:'copy'
    input:
    tuple val(meta), path(bam, stageAs:'sample.bam'), path(bai, stageAs:'sample.bam.bai')
    tuple path(fasta, stageAs:'reference.fa'), path(fai, stageAs:'reference.fa.fai'), val(validated)
    path assets, stageAs: 'assets'
    val tier
    output:
    tuple val(meta), path('nasvar'), emit: results
    script:
    """
    run_nasvar.py --sample '${meta.id}' --tier '${tier}' --bam sample.bam \
      --fasta reference.fa --repeats assets/repeats.bed --enriched assets/enrichment.bed \
      --sites assets/sites.tsv --targets assets/targets.bed --gff assets/genes.gff3 \
      --config assets/pipeline.json --reference assets/reference.json
    """
    stub:
    """
    mkdir nasvar
    echo '{"stub":true,"tier":"${tier}"}' > 'nasvar/${meta.id}.result.json'
    echo '<html>stub</html>' > 'nasvar/${meta.id}.report.html'
    echo 'nasvar: stub' > nasvar/versions.txt
    """
}
