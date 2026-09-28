process SAMPLE_SUMMARY {
    tag "${meta.id}"
    container { params.images.summary }
    input:
    tuple val(meta), val(analyses), path(files, stageAs:'inputs/??/*')
    val context
    path template, stageAs:'template.qmd'
    output:
    tuple val(meta), path('summary/*.html'), path('summary/*.json'), emit: results
    path 'summary.versions.yml', emit: versions
    script:
    def payload = groovy.json.JsonOutput.toJson(context + [analyses:analyses]).bytes.encodeBase64().toString()
    """
    python3 -c 'import base64; from pathlib import Path; Path("context.json").write_bytes(base64.b64decode("${payload}"))'
    sample_summary.py --sample '${meta.id}' --inputs inputs --context context.json --template template.qmd
    quarto render 'summary/${meta.id}.summary.qmd' --to html
    quarto --version > summary.versions.yml
    """
    stub:
    """
    mkdir summary
    echo '<html><body>${meta.id} summary stub</body></html>' > summary/${meta.id}.summary.html
    echo '{"sample":"${meta.id}","stub":true}' > summary/${meta.id}.summary.json
    echo 'quarto: stub' > summary.versions.yml
    """
}
