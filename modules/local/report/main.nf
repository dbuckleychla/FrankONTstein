process PUBLISH_ARTIFACT {
    tag "${meta.id}:${analysis}"
    container { params.images.preprocess }
    publishDir { "${params.outdir}/${meta.id}/${OutputLayout.directory(analysis)}" }, mode: 'copy', pattern: 'artifacts/*', saveAs: { name -> name.replaceFirst('artifacts/', '') }
    input:
    tuple val(meta), val(analysis), path(files, stageAs:'source/*')
    output:
    tuple val(meta), val(analysis), path('artifacts/*'), emit: results
    script:
    // These callers emit a wrapper directory; publish its contents under the analysis.
    def paths = files instanceof List ? files : [files]
    def isLog = paths.every { it.name in ['SUBCHROM','ICHORCNA','HMMCOPY_WIG'] }
    def source = analysis in ['nasvar', 'ichorcna', 'subchrom', 'qc'] && !isLog ? 'source/*/.' : 'source/*'
    """
    mkdir artifacts
    cp -RL ${source} artifacts/
    ${analysis == 'methylation' ? "audit_classy.py 'artifacts/classy/${meta.id}_combined_classification.json'" : ''}
    name_sample_artifacts.py artifacts '${meta.id}'
    """
}
process RESULTS_INDEX {
    container { params.images.preprocess }
    publishDir params.outdir, mode:'copy'
    input:
    val records
    val provenance
    path versions
    path qc_metrics, stageAs: 'qc_metrics/??/metrics.json'
    output:
    path 'manifest.json'
    path 'index.html'
    script:
    def payload = groovy.json.JsonOutput.toJson([run:provenance, analyses:records, software_versions:'pipeline_info/versions.json']).bytes.encodeBase64().toString()
    """
    make_report.py '${payload}' --qc-dir qc_metrics
    """
}

process SOFTWARE_VERSIONS {
    container { params.images.preprocess }
    publishDir "${params.outdir}/pipeline_info", mode:'copy'
    input:
    path files, stageAs:'software/??/*'
    output:
    path 'versions.json'
    script:
    """
    python3 - <<'PY'
    import json
    from pathlib import Path
    versions = {str(p): p.read_text() for p in Path('software').glob('*/*') if p.is_file()}
    Path('versions.json').write_text(json.dumps(versions, indent=2))
    PY
    """
}
