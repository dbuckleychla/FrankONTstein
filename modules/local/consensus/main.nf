process SOMATIC_CONSENSUS {
    tag "${meta.id}"
    container { params.images.preprocess }
    input:
    tuple val(meta), path(ds, stageAs:'deepsomatic/*'), path(cs, stageAs:'clairsto/*')
    tuple path(fasta, stageAs:'reference.fa'), path(fai, stageAs:'reference.fa.fai'), val(validated)
    path assets
    output:
    tuple val(meta), path('consensus/*'), emit: results
    path 'consensus.versions.yml', emit: versions
    script:
    """
    somatic_consensus.py --sample '${meta.id}' --deepsomatic deepsomatic/*.vcf.gz --clairsto clairsto/*.vcf.gz \\
      --fasta reference.fa --fai reference.fa.fai --config '${assets}/pipeline.json' \\
      --gff '${assets}/genes.gff3' --reference '${assets}/reference.json' --output consensus --image '${task.container}'
    python3 -c 'import pysam; print("pysam: " + pysam.__version__)' > consensus.versions.yml
    """
    stub:
    """
    mkdir consensus
    touch consensus/${meta.id}.consensus.snv.vcf.gz consensus/${meta.id}.consensus.snv.vcf.gz.tbi
    touch consensus/${meta.id}.consensus.indel.vcf.gz consensus/${meta.id}.consensus.indel.vcf.gz.tbi
    echo '{"sample":"${meta.id}","status":"completed","counts":{"snv":0,"indel":0},"queries":[],"evidence":[]}' > consensus/${meta.id}.consensus.json
    echo 'pysam: stub' > consensus.versions.yml
    """
}
