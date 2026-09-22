nextflow.enable.dsl=2
include { ADAPTIVE } from './workflows/adaptive'

def runState = [samples:[], provenance:[:], completed:Collections.synchronizedList([]), failureTask:null, error:null]

workflow {
    if (params.help) {
        log.info '''FrankONTstein: ONT tumor-only adaptive sampling
Required: --bam FILE --sample_id ID OR --input manifest.csv
          --reference_bundle bundle.json --targets_bed targets.bed
          --enrichment_bed enrichment.bed --image_manifest images.json
Tier:     --primary (default), --secondary, or --tertiary
Optional: --demux_samplesheet demux.csv --trim --callers nasvar,sniffles
Profiles: -profile local,docker | slurm,apptainer | aws
'''
    } else {
        if ((!params.bam && !params.input) || (params.bam && params.input)) error 'Choose --bam or --input'
        for (required in ['reference_bundle','targets_bed','enrichment_bed','image_manifest']) {
            if (!params[required]) error "Missing required --${required}"
        }
        def bundlePath = file(params.reference_bundle, checkIfExists:true)
        def bundle = WorkflowPlan.readJson(bundlePath)
        if (params.sequencing_kit) WorkflowPlan.identifier(params.sequencing_kit.toString())
        def plan = WorkflowPlan.resolve(params as Map, bundle)
        def imageLock = WorkflowPlan.readJson(file(params.image_manifest, checkIfExists:true))
        def neededImages = (['preprocess','classy'] + plan.callers).unique()
        if (plan.callers.intersect(['clair3','clairsto']) && !neededImages.contains('bcftools')) neededImages += 'bcftools'
        neededImages.each { name ->
            if (!(imageLock[name] ==~ /[^\s]+@sha256:[a-f0-9]{64}/)) error "Image ${name} must have a sha256 digest in --image_manifest"
        }
        def assetPath = { value ->
            if (!value) error 'Missing selected analysis reference asset'
            def s = value.toString()
            def resolved = s.contains('://') || s.startsWith('/') ? s : bundlePath.parent.resolve(s).toString()
            file(resolved, checkIfExists:true)
        }
        def fasta = assetPath(bundle.fasta)
        def fai = assetPath(bundle.fai)
        if (fai.name != fasta.name + '.fai') error 'FASTA index basename must be FASTA basename + .fai'
        def assets = [enrichment:file(params.enrichment_bed, checkIfExists:true), targets:file(params.targets_bed, checkIfExists:true)]
        ['repeats','gff','sites','config','reference'].each { name ->
            assets[name] = plan.callers.contains('nasvar') ? assetPath(bundle.nasvar?.get(name)) : []
        }
        def resources = [:]
        if (plan.callers.contains('clair3')) resources.clair3_model = assetPath(bundle.models?.clair3)
        if (plan.callers.contains('clairsto')) {
            resources.clairsto_model = bundle.models?.clairsto
            WorkflowPlan.identifier(resources.clairsto_model as String)
        }
        ['stellerator':'fusion_list', 'delly':'delly_map', 'subchrom':'subchrom_panel'].each { caller,key ->
            if (plan.callers.contains(caller)) resources[key] = assetPath(bundle.callers?.get(key))
        }
        if (plan.callers.contains('ichorcna')) {
            ['ichor_gc','ichor_map','ichor_centromeres','ichor_panel','ichor_seqinfo'].each { key -> resources[key] = assetPath(bundle.callers?.get(key)) }
        }
        if (params.clair3_gpu && workflow.profile.tokenize(',').contains('aws') && !params.aws_gpu_queue) error '--clair3_gpu on AWS requires --aws_gpu_queue'
        if (workflow.profile.tokenize(',').contains('aws') && (!params.aws_queue || !params.aws_region || !params.aws_job_role || !workflow.workDir.toString().startsWith('s3://'))) {
            error 'AWS requires --aws_queue, --aws_region, --aws_job_role and -work-dir s3://...'
        }
        demux = params.demux_samplesheet ? Channel.fromPath(params.demux_samplesheet, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([])
        sampleRows = params.input ? Channel.fromPath(params.input, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([[sample:params.sample_id, run:params.sample_id, bam:params.bam]])
        samples = sampleRows.map { [rows:it] }.combine(demux.map { [mapping:it] }).flatMap { left, right ->
            def rows = left.rows
            def mapping = right.mapping
            def grouped = WorkflowPlan.samples(rows, mapping, params.demux_samplesheet != null, params.sequencing_kit as String)
            runState.samples = params.demux_samplesheet ? mapping*.sample.unique() : rows*.sample.unique()
            grouped.collect { meta, paths -> tuple(meta, paths.collect { file(it, checkIfExists:true) }) }
        }

        def provenance = [plan:plan, bundle:bundle, images:imageLock, dependencies:WorkflowPlan.readJson(file("${projectDir}/dependencies.json")), nextflow:nextflow.version.toString(), command:workflow.commandLine, session_id:workflow.sessionId.toString(), stub:workflow.stubRun]
        def parameterNames = ['bam','sample_id','input','demux_samplesheet','trim','sequencing_kit','genome','reference_bundle','targets_bed','enrichment_bed','callers','max_cpus','max_memory','max_time','qdnaseq_binsize','delly_bin_size','ichor_bin_size','clair3_gpu']
        provenance.parameters = parameterNames.collectEntries { key -> [(key):params[key]] }
        runState.provenance = provenance
        ADAPTIVE(samples, Channel.value(tuple(fasta,fai)), assets, plan, resources, provenance, runState)
    }
}

workflow.onComplete {
    if (params.help) return
    def info = file("${params.outdir}/pipeline_info")
    info.mkdirs()
    if (!workflow.success) {
        // Metadata errorMessage may be empty when a task fails before stderr exists.
        def taskFault = nextflow.Global.session.fault
        runState.failureTask = taskFault?.task?.name ?: runState.failureTask
        runState.error = taskFault?.error?.message ?: runState.error
        def summaryTrace = 'name\tstatus\n' + runState.completed.collect { item -> "PUBLISH_ARTIFACT (${item.sample}:${item.analysis})\tCOMPLETED\n" }.join('')
        if (runState.failureTask) summaryTrace += "${runState.failureTask}\tFAILED\n"
        def analyses = RunStatus.summarize(runState.samples, runState.provenance.plan?.callers ?: [], summaryTrace)
        file("${params.outdir}/manifest.json").text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson([
            run:runState.provenance, status:'failed', error:runState.error ?: workflow.errorMessage, analyses:analyses,
            task_statuses:'pipeline_info/trace.tsv'
        ]))
        file("${params.outdir}/index.html").text = '<!doctype html><meta charset="utf-8"><title>FrankONTstein failed run</title><h1>Run failed</h1><p>See <a href="manifest.json">manifest.json</a> for analysis statuses and <a href="pipeline_info/trace.tsv">trace.tsv</a> for task details. Completed artifacts may be present.</p>'
    }
    info.resolve('status.json').text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson([
        status:workflow.success ? 'completed' : 'failed', exit_status:workflow.exitStatus,
        error:runState.error ?: workflow.errorMessage, completed:workflow.complete?.toString(), run:workflow.runName
    ]))
}

workflow.onError { fault ->
    runState.error = workflow.errorReport ?: workflow.errorMessage ?: fault?.toString()
    if (fault?.hasProperty('task')) runState.failureTask = fault.task?.name
    else if (fault?.hasProperty('name')) runState.failureTask = fault.name
}
