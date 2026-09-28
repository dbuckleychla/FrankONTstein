process VALIDATE_REFERENCE {
    container { params.images.preprocess }
    publishDir { "${params.outdir}/pipeline_info" }, mode: 'copy', pattern: 'reference_audit'
    input:
    tuple path(fasta, stageAs:'reference.fa'), path(fai, stageAs:'reference.fa.fai')
    path enrichment, stageAs:'input/enrichment.bed'
    path targets, stageAs:'input/targets.bed'
    path repeats, stageAs:'input/repeats.bed'
    path gff, stageAs:'input/genes.gff3'
    path sites, stageAs:'input/sites.tsv'
    path pipeline, stageAs:'input/pipeline.json'
    path reference_config, stageAs:'input/reference.json'
    val nasvar_enabled
    output:
    tuple path('reference.fa'), path('reference.fa.fai'), val(true), emit: reference
    path 'assets', emit: assets
    path 'reference_audit', optional: true, emit: audit
    script:
    def extra = nasvar_enabled ? '--reference-config assets/reference.json --bed assets/repeats.bed --gff assets/genes.gff3 --sites assets/sites.tsv' : ''
    """
    mkdir assets
    cp -L input/* assets/
    ${nasvar_enabled ? 'prepare_reference_assets.py reference.fa.fai assets; mkdir reference_audit; cp assets/reference_audit.json assets/repeats.excluded.bed reference_audit/' : ''}
    check_reference.py reference.fa.fai --fasta reference.fa --bed assets/enrichment.bed --bed assets/targets.bed ${extra}
    """
}
