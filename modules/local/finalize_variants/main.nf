process FINALIZE_VARIANTS {
    tag "${meta.id}:${caller}:${kind}"
    container { params.images.preprocess }
    input:
    tuple val(meta), val(caller), val(kind), path(vcf)
    path fai
    output:
    tuple val(meta), val(caller), path('variants/*'), emit: results
    path 'variant_filter.versions.yml', emit: versions
    script:
    """
    finalize_variants.py --input '${vcf}' --fai '${fai}' --sample '${meta.id}' \\
        --caller '${caller}' --prefix '${meta.id}.${kind}'
    python3 -c 'import pysam; print("pysam: " + pysam.__version__)' > variant_filter.versions.yml
    """
    stub:
    """
    mkdir variants
    touch 'variants/${meta.id}.${kind}.normalized.vcf.gz' 'variants/${meta.id}.${kind}.normalized.vcf.gz.tbi'
    touch 'variants/${meta.id}.${kind}.pass.vcf.gz' 'variants/${meta.id}.${kind}.pass.vcf.gz.tbi'
    echo '{"stub":true}' > 'variants/${meta.id}.${kind}.filtering.json'
    echo 'pysam: stub' > variant_filter.versions.yml
    """
}
