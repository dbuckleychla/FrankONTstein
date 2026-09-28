// Local wrapper adds an explicit, staged target BED to indexed pileup.
process BCFTOOLS_MPILEUP {
    tag "${meta.id}"
    container { params.images.bcftools }
    input:
    tuple val(meta), path(bam), path(bam_bai), path(ref), path(ref_fai)
    path assets
    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta), path("${meta.id}.bcf"), emit: bcf
    path 'versions.yml', emit: versions
    script:
    """
    source capture_task_logs.sh BCFTOOLS_MPILEUP
    bcftools mpileup -Ob --min-BQ 0 --threads ${task.cpus} \\
        --regions-file '${assets}/targets.bed' \\
        -f '${ref}' '${bam}' -o '${meta.id}.bcf'
    bcftools --version > versions.yml
    """
    stub:
    """
    source capture_task_logs.sh BCFTOOLS_MPILEUP
    test -s '${assets}/targets.bed'
    touch '${meta.id}.bcf'
    echo 'bcftools: stub' > versions.yml
    """
}
