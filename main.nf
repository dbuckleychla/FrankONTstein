include { PRIMARY; SECONDARY; TERTIARY; REPORTING } from './workflows/adaptive'

workflow {
    def runState = [samples:[], provenance:[:], inputGroups:[:], completed:Collections.synchronizedList([]), failureTask:null, error:null]
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
POD5:     --basecall --pod5 FILE_OR_DIRECTORY --sample_id ID (or POD5 manifest)
          steps.basecall.model and steps.basecall.modified_models in params YAML
Resources: --basecall_cpus 4 --basecall_memory '16 GB' (per GPU chunk)
GPU:      --gpu_queue (Slurm), --aws_gpu_queue (AWS), or --basecall_device (local)
          --genome hg38 --fasta reference.fa (or --reference_bundle bundle.json)
          --targets_bed targets.bed
          --enrichment_bed enrichment.bed --image_manifest images.json
Tier:     --primary (default), --secondary, or --tertiary
Optional: --demux_samplesheet demux.csv --trim --sequencing_kit KIT_NAME
          --callers nasvar,sniffles --basecall_model sup|hac|fast
QC:       --disable-qc true skips comprehensive QC, retaining CpG bedMethyl.
Demux sheet: local CSV path or s3://bucket/key.csv.
             experiment_id,kit,barcode,alias (extra sequencer columns accepted).
Trimming requires --sequencing_kit or the demux sheet's kit column.
Profiles: -profile local,docker | slurm,apptainer | aws
'''
    } else {
        if (workflow.profile.tokenize(',').contains('aws')) WorkflowPlan.validateAws(params as Map, workflow.workDir)
        def basecalling = Basecalling.validate(params as Map, (nextflow.Global.config.process.executor ?: 'local').toString(), workflow.profile)
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
        def basecallModels = basecalling.enabled ? [model:projectPath.call(params.steps.basecall.model), modified:params.steps.basecall.modified_models.collect { projectPath.call(it) }] : [:]
        def assets = [basecall_models:basecallModels, basecalling:basecalling, enrichment:projectPath.call(params.enrichment_bed), targets:projectPath.call(params.targets_bed)]
        ['repeats','gff','sites','config','reference'].each { name ->
            assets[name] = plan.callers.contains('nasvar') ? assetPath.call(bundle.nasvar?.get(name)) : []
        }
        def externalClair3 = plan.callers.contains('clair3') && params.steps?.clair3?.model ? projectPath.call(params.steps.clair3.model) : []
        assets.clair3_model = externalClair3
        def resources = [clair3_model:externalClair3]
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
        demux = params.demux_samplesheet ? Channel.fromPath(params.demux_samplesheet, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([])
        sampleRows = params.input ? Channel.fromPath(params.input, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([[sample:params.sample_id, run:params.sample_id, bam:params.bam, pod5:params.pod5]])
        samples = sampleRows.map { [rows:it] }.combine(demux.map { [mapping:it] }).flatMap { left, right ->
            def rows = Basecalling.rows(left.rows, basecalling.enabled)
            def mapping = params.demux_samplesheet ? WorkflowPlan.demuxRows(right.mapping) : []
            def grouped = WorkflowPlan.samples(rows, mapping, params.demux_samplesheet != null, params.sequencing_kit as String)
            runState.samples = params.demux_samplesheet ? mapping.collect { it.sample }.unique() : rows.collect { it.sample }.unique()
            runState.inputGroups = grouped.collectEntries { meta, paths -> [(meta.id):meta.mappings ? meta.mappings.collect { it.sample } : [meta.id]] }
            def seenPod5 = [] as Set
            grouped.collect { meta, paths ->
                if (externalClair3) meta.require_moves = true
                if (!basecalling.enabled) return tuple(meta, paths.collect { file(it, checkIfExists:true) })
                def resolved = paths.collectMany { value ->
                    def source = value.toString()
                    def selectedFiles = source.endsWith('.pod5') ? [file(source, checkIfExists:true)] : files(source.replaceAll('/+$', '') + '/*.pod5', checkIfExists:true)
                    selectedFiles.collect { it.toUri().scheme == 'file' ? it.toRealPath() : it.normalize() }
                }
                resolved.each { path ->
                    if (!seenPod5.add(path.toString())) error "Duplicate resolved POD5 input: ${path}"
                }
                tuple(meta, resolved)
            }
        }

        def provenance = [basecalling:basecalling, plan:plan, bundle:bundle, images:imageLock, dependencies:WorkflowPlan.readJson(file("${projectDir}/dependencies.json")), nextflow:nextflow.version.toString(), command:workflow.commandLine, session_id:workflow.sessionId.toString(), stub:workflow.stubRun]
        def parameterNames = ['basecall','pod5','basecall_cpus','basecall_memory','basecall_tasks','basecall_max_forks','basecall_device','bam','sample_id','input','demux_samplesheet','trim','sequencing_kit','genome','reference_bundle','targets_bed','enrichment_bed','callers','max_cpus','max_memory','max_time','qdnaseq_binsize','delly_bin_size','ichor_bin_size','clair3_gpu','basecall_model','disable_qc']
        provenance.parameters = parameterNames.collectEntries { key -> [(key):params[key]] }
        provenance.parameters.basecall_assets = params.steps?.basecall
        provenance.parameters.disable_qc = WorkflowPlan.qcDisabled(params as Map)
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
        REPORTING(PRIMARY.out.bam, artifacts, versions, plan, provenance, runState, PRIMARY.out.qc_metrics, PRIMARY.out.basecall_records)
    }
}
