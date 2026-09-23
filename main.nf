include { PRIMARY; SECONDARY; TERTIARY; REPORTING } from './workflows/adaptive'

workflow {
    def runState = [samples:[], provenance:[:], completed:Collections.synchronizedList([]), failureTask:null, error:null]
    def workflowMeta = workflow
    def outputDir = file(params.outdir)
    def showHelp = params.help.toString().toBoolean()
    workflow.onComplete {
        if (!showHelp) RunStatus.finish(workflowMeta, runState, outputDir)
    }
    workflow.onError { fault ->
        runState.error = workflowMeta.errorReport ?: workflowMeta.errorMessage ?: fault?.toString()
    }

    if (showHelp) {
        log.info '''FrankONTstein: ONT tumor-only adaptive sampling
Required: --bam FILE --sample_id ID OR --input manifest.csv
          --genome hg38 --fasta reference.fa (or --reference_bundle bundle.json)
          --targets_bed targets.bed
          --enrichment_bed enrichment.bed --image_manifest images.json
Tier:     --primary (default), --secondary, or --tertiary
Optional: --demux_samplesheet demux.csv --trim --sequencing_kit KIT_NAME
          --callers nasvar,sniffles --basecall_model sup|hac|fast
Trimming requires --sequencing_kit or the demux sheet's kit column.
Profiles: -profile local,docker | slurm,apptainer | aws
'''
    } else {
        if ((!params.bam && !params.input) || (params.bam && params.input)) error 'Choose --bam or --input'
        ['targets_bed','enrichment_bed','image_manifest'].each { required ->
            if (!params[required]) error "Missing required --${required}"
        }
        def projectPath = { value ->
            def s = value.toString()
            file(s.contains('://') || s.startsWith('/') ? s : projectDir.resolve(s).toString(), checkIfExists:true)
        }
        def bundlePath = params.reference_bundle ? projectPath.call(params.reference_bundle) : null
        def bundle = WorkflowPlan.reference(params as Map, bundlePath ? WorkflowPlan.readJson(bundlePath) : [:], projectDir.toString())
        if (params.sequencing_kit) WorkflowPlan.identifier(params.sequencing_kit.toString())
        def plan = WorkflowPlan.resolve(params as Map, bundle)
        def imageLock = WorkflowPlan.readJson(projectPath.call(params.image_manifest))
        def neededImages = (['preprocess','classy'] + plan.callers).unique()
        if (plan.callers.intersect(['clair3','clairsto']) && !neededImages.contains('bcftools')) neededImages += 'bcftools'
        neededImages.each { name ->
            if (!(imageLock[name] ==~ /[^\s]+@sha256:[a-f0-9]{64}/)) error "Image ${name} must have a sha256 digest in --image_manifest"
        }
        def assetPath = { value ->
            if (!value) error 'Missing selected analysis reference asset'
            def s = value.toString()
            def resolved = s.contains('://') || s.startsWith('/') ? s : (bundlePath ? bundlePath.parent.resolve(s).toString() : projectDir.resolve(s).toString())
            file(resolved, checkIfExists:true)
        }
        def fasta = assetPath.call(bundle.fasta)
        def fai = assetPath.call(bundle.fai)
        if (fai.name != fasta.name + '.fai') error 'FASTA index basename must be FASTA basename + .fai'
        def assets = [enrichment:projectPath.call(params.enrichment_bed), targets:projectPath.call(params.targets_bed)]
        ['repeats','gff','sites','config','reference'].each { name ->
            assets[name] = plan.callers.contains('nasvar') ? assetPath.call(bundle.nasvar?.get(name)) : []
        }
        def resources = [:]
        if (plan.callers.contains('clairsto')) {
            resources.clairsto_model = bundle.models?.clairsto
            WorkflowPlan.identifier(resources.clairsto_model as String)
        }
        ['stellerator':'fusion_list', 'delly':'delly_map', 'subchrom':'subchrom_panel'].each { caller,key ->
            if (plan.callers.contains(caller)) resources[key] = assetPath.call(bundle.callers?.get(key))
        }
        if (plan.callers.contains('ichorcna')) {
            ['ichor_gc','ichor_map','ichor_centromeres','ichor_panel','ichor_seqinfo'].each { key -> resources[key] = assetPath.call(bundle.callers?.get(key)) }
        }
        if (params.clair3_gpu.toString().toBoolean() && workflow.profile.tokenize(',').contains('aws') && !params.aws_gpu_queue) error '--clair3_gpu on AWS requires --aws_gpu_queue'
        if (workflow.profile.tokenize(',').contains('aws') && (!params.aws_queue || !params.aws_region || !params.aws_job_role || !workflow.workDir.toString().startsWith('s3://'))) {
            error 'AWS requires --aws_queue, --aws_region, --aws_job_role and -work-dir s3://...'
        }
        demux = params.demux_samplesheet ? Channel.fromPath(params.demux_samplesheet, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([])
        sampleRows = params.input ? Channel.fromPath(params.input, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([[sample:params.sample_id, run:params.sample_id, bam:params.bam]])
        samples = sampleRows.map { [rows:it] }.combine(demux.map { [mapping:it] }).flatMap { left, right ->
            def rows = left.rows
            def mapping = right.mapping
            def grouped = WorkflowPlan.samples(rows, mapping, params.demux_samplesheet != null, params.sequencing_kit as String)
            runState.samples = params.demux_samplesheet ? mapping.collect { it.sample }.unique() : rows.collect { it.sample }.unique()
            grouped.collect { meta, paths -> tuple(meta, paths.collect { file(it, checkIfExists:true) }) }
        }

        def provenance = [plan:plan, bundle:bundle, images:imageLock, dependencies:WorkflowPlan.readJson(file("${projectDir}/dependencies.json")), nextflow:nextflow.version.toString(), command:workflow.commandLine, session_id:workflow.sessionId.toString(), stub:workflow.stubRun]
        def parameterNames = ['bam','sample_id','input','demux_samplesheet','trim','sequencing_kit','genome','reference_bundle','targets_bed','enrichment_bed','callers','max_cpus','max_memory','max_time','qdnaseq_binsize','delly_bin_size','ichor_bin_size','clair3_gpu','basecall_model']
        provenance.parameters = parameterNames.collectEntries { key -> [(key):params[key]] }
        runState.provenance = provenance
        PRIMARY(samples, Channel.value(tuple(fasta,fai)), assets, plan, runState)
        artifacts = PRIMARY.out.results
        versions = PRIMARY.out.software
        if (plan.tier == 'secondary') {
            SECONDARY(PRIMARY.out.bam, PRIMARY.out.reference, PRIMARY.out.reference_assets)
            artifacts = artifacts.mix(SECONDARY.out.results)
            versions = versions.mix(SECONDARY.out.software)
        } else if (plan.tier == 'tertiary') {
            TERTIARY(PRIMARY.out.bam, PRIMARY.out.reference, PRIMARY.out.reference_assets, plan, resources)
            artifacts = artifacts.mix(TERTIARY.out.results)
            versions = versions.mix(TERTIARY.out.software)
        }
        REPORTING(PRIMARY.out.bam, artifacts, versions, plan, provenance, runState)
    }
}
