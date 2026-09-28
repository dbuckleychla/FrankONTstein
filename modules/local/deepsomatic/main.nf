process DEEPSOMATIC {
    tag "${meta.id}"
    container { params.images.deepsomatic }
    input:
    tuple val(meta), path(bam), path(bai)
    tuple path(ref), path(fai), val(validated)
    path assets
    output:
    tuple val(meta), path('results/somatic.vcf.gz'), emit: vcf
    tuple val(meta), path('results/*'), emit: results
    path 'versions.yml', emit: versions
    script:
    def gpu = WorkflowPlan.deepsomaticGpu(params as Map, workflow.profile)
    """
    run_deepsomatic_task.py --bam '${bam}' --ref '${ref}' \\
        --targets '${assets}/targets.bed' --sample '${meta.id}' \\
        --cpus ${task.cpus} --image '${params.images.deepsomatic}' ${gpu ? '--gpu' : ''}
    """
    stub:
    """
    test -s '${assets}/targets.bed'
    mkdir -p results/logs
    touch results/somatic.vcf.gz results/somatic.vcf.gz.tbi
    echo 'stub: no inference' > results/logs/runner.log
    echo '{"stub":true,"model_type":"ONT_TUMOR_ONLY"}' > results/provenance.json
    echo 'DeepSomatic: stub' > versions.yml
    """
}
