process CHECK_BASECALL_MODELS {
    cache 'deep'
    container { params.images.preprocess }
    publishDir { "${params.outdir}/basecalling" }, mode: 'copy', pattern: 'models.json'
    input:
    path model, stageAs: 'models/base/*'
    path modified, stageAs: 'models/mod/*'
    val clair3
    path clair3_model, stageAs: 'models/clair3/*'
    output:
    path 'models.json', emit: provenance
    script:
    def external = clair3_model ? "--clair3-model ${Basecalling.quote(clair3_model)}" : ''
    """
    check_basecall_models.py --model ${Basecalling.quote(model)} --modified ${Basecalling.quote(modified)} ${clair3 ? "--clair3 '${params.basecall_model}'" : ''} ${external} > models.json
    """
    stub:
    """
    echo '{"stub":true}' > models.json
    """
}

process DORADO_BASECALL {
    tag "${meta.id}:${batch}"
    container { params.images.preprocess }
    maxForks (params.basecall_max_forks ?: (workflow.profile.tokenize(',').intersect(['slurm','aws']) ? 32 : 1))
    publishDir { "${params.outdir}/basecalling/${meta.id}" }, mode: 'copy', pattern: '*.log'
    input:
    tuple val(meta), val(batch), path(pod5, stageAs: 'pod5_inputs/input????????.pod5')
    path model, stageAs: 'models/base/*'
    path modified, stageAs: 'models/mod/*'
    path provenance
    output:
    tuple val(meta), val(batch), path("${batch}.bam"), emit: bam
    path "${batch}.versions.yml", emit: versions
    tuple val(meta), path("${batch}.log"), emit: log
    script:
    """
    nvidia-smi --query-gpu=uuid --format=csv,noheader | tee '${batch}.log'
    test -s '${batch}.log' || { echo 'No NVIDIA GPU is visible' >&2; exit 1; }
    echo 'Starting Dorado chunk ${batch}' | tee -a '${batch}.log'
    dorado basecaller ${Basecalling.quote(model)} pod5_inputs --modified-bases-models ${Basecalling.quote(modified)} --no-trim --emit-moves --device cuda:all 2>&1 > '${batch}.bam' | tee -a '${batch}.log' >&2
    samtools quickcheck -u '${batch}.bam'
    echo 'Dorado chunk ${batch} completed; BAM quickcheck passed' | tee -a '${batch}.log'
    dorado --version > '${batch}.versions.yml' 2>&1
    """
    stub:
    """
    touch '${batch}.bam'
    echo 'stub: no GPU or basecalling validation' > '${batch}.log'
    echo 'dorado: stub' > '${batch}.versions.yml'
    """
}
