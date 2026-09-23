class RunStatus {
    static void finish(workflow, Map runState, outputDir) {
        def info = outputDir.resolve('pipeline_info')
        info.mkdirs()
        if (!workflow.success) {
            // Metadata errorMessage may be empty when a task fails before stderr exists.
            def taskFault = nextflow.Global.session.fault
            runState.failureTask = taskFault?.task?.name ?: runState.failureTask
            runState.error = taskFault?.error?.message ?: runState.error
            def summaryTrace = 'name\tstatus\n' + runState.completed.collect { item -> "PUBLISH_ARTIFACT (${item.sample}:${item.analysis})\tCOMPLETED\n" }.join('')
            if (runState.failureTask) summaryTrace += "${runState.failureTask}\tFAILED\n"
            def analyses = RunStatus.summarize(runState.samples, (runState.provenance.plan?.callers ?: []) + ['bedmethyl','qc'], summaryTrace)
            analyses.each { row ->
                row.files = runState.completed.findAll { it.sample == row.sample && it.analysis == row.analysis }.collectMany { it.files ?: [] }.unique()
                if (row.analysis == 'qc' && runState.provenance.parameters?.disable_qc?.toString() == 'true') row.status = 'skipped'
            }
            outputDir.resolve('manifest.json').text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson([
                run:runState.provenance, status:'failed', error:runState.error ?: workflow.errorMessage, analyses:analyses,
                task_statuses:'pipeline_info/trace.tsv'
            ]))
            outputDir.resolve('index.html').text = '<!doctype html><meta charset="utf-8"><title>FrankONTstein failed run</title><h1>Run failed</h1><p>See <a href="manifest.json">manifest.json</a> for analysis statuses and <a href="pipeline_info/trace.tsv">trace.tsv</a> for task details. Completed artifacts may be present.</p>' + analyses.findAll { it.files }.collect { row -> '<p>' + row.files.collect { path -> '<a href="' + path.replace('&','&amp;').replace('"','&quot;').replace('<','&lt;') + '">' + path.replace('&','&amp;').replace('<','&lt;') + '</a>' }.join(' ') + '</p>' }.join('')
        }
        info.resolve('status.json').text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson([
            status:workflow.success ? 'completed' : 'failed', exit_status:workflow.exitStatus,
            error:runState.error ?: workflow.errorMessage, completed:workflow.complete?.toString(), run:workflow.runName
        ]))
    }

    static List summarize(List samples, List callers, String trace) {
        def aliases = [MODKIT_PILEUP:'bedmethyl', INDEX_BEDMETHYL:'bedmethyl', SAMPLE_QC:'qc', ALIGN:'alignment', CLASSY_COMBINED:'methylation', NASVAR:'nasvar', CLAIR3:'clair3',
            CLAIRS_TO_CALL:'clairsto', BCFTOOLS_MPILEUP:'bcftools', BCFTOOLS_CALL:'bcftools',
            SNIFFLES_CALL:'sniffles', SEVERUS_TUMOR_UNPHASED:'severus', STELLERATOR:'stellerator',
            QDNASEQ_CALL:'qdnaseq', DELLY:'delly', SUBCHROM:'subchrom', ICHORCNA:'ichorcna']
        def outcomes = [:]
        def lines = trace.readLines()
        if (lines) {
            def header = lines[0].split('\t') as List
            lines.drop(1).each { line ->
                def values = line.split('\t', -1)
                def name = values[header.indexOf('name')]
                def status = values[header.indexOf('status')]
                def match = name =~ /(?:^|:)([A-Z_0-9]+) \(([^:()]+)(?::([^()]+))?\)$/
                if (match.find()) {
                    def process = match.group(1)
                    def sample = match.group(2)
                    def analysis = process == 'PUBLISH_ARTIFACT' ? match.group(3) : process == 'FILTER_VARIANTS' ? match.group(3)?.tokenize(':')?.getAt(0) : aliases[process]
                    if (analysis) {
                        def key = [sample,analysis]
                        if (status == 'FAILED') outcomes[key] = 'failed'
                        else if (status in ['COMPLETED','CACHED'] && process in ['PUBLISH_ARTIFACT','ALIGN'] && outcomes[key] != 'failed') outcomes[key] = 'completed'
                    }
                }
            }
        }
        samples.collectMany { sample ->
            (['alignment','methylation'] + callers).collect { analysis ->
                [sample:sample, analysis:analysis, status:outcomes[[sample,analysis]] ?: 'not_completed', files:[]]
            }
        }
    }
}
