// Local orchestration of the pinned ClairS-TO runtime; vendor gitlinks unchanged.
process CLAIRS_TO_CALL {
    tag "${meta.id}"
    container { params.images.clairsto }
    input:
    tuple val(meta), path(bam), path(bai), path(ref), path(ref_idx), val(model)
    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta), path("${meta.id}/snv*.vcf.gz"), emit: snv
    tuple val(meta), path("${meta.id}/indel*.vcf.gz"), emit: indel
    path 'versions.yml', emit: versions
    script:
    def gpu = WorkflowPlan.clairstoGpu(params as Map, workflow.profile)
    // Upstream uses --threads as concurrent prediction workers, each loading models.
    def threads = gpu ? Math.min(params.clairsto_gpu_threads as int, task.cpus as int) : task.cpus
    def gpuCheck = gpu ? "python -c \"import torch; assert torch.version.cuda is not None, 'ClairS-TO PyTorch lacks CUDA support'; assert torch.cuda.is_available(), 'ClairS-TO cannot access its assigned GPU'\"" : ''
    """
    source capture_task_logs.sh CLAIRS_TO_CALL
    ${gpuCheck}
    run_clairs_to --threads ${threads} -s '${meta.id}' \
        --tumor_bam_fn '${bam}' --ref_fn '${ref}' --platform '${model}' \
        -o '${meta.id}' ${gpu ? '--use_gpu' : ''}
    run_clairs_to --version > versions.yml 2>&1
    """
    stub:
    """
    source capture_task_logs.sh CLAIRS_TO_CALL
    mkdir '${meta.id}'
    touch '${meta.id}/snv.vcf.gz' '${meta.id}/indel.vcf.gz'
    echo 'ClairS-TO: stub' > versions.yml
    """
}
