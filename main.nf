include { PRIMARY; SECONDARY; TERTIARY; REPORTING } from './workflows/adaptive'

workflow {
    if (!(params.max_retries.toString() ==~ /0|[1-9][0-9]*/)) error '--max_retries must be a nonnegative integer'
    def runState = [samples:[], provenance:[:], inputGroups:[:], completed:Collections.synchronizedList([]), failureTask:null, error:null]
    def workflowMeta = workflow
    if (!params.help.toString().toBoolean()) WorkflowPlan.validateRunId(params as Map,
        workflow.profile.tokenize(',').contains('aws') && !!(System.getenv('FRANKONTSTEIN_WORK_PREFIX') || System.getenv('FRANKONTSTEIN_RESULTS_PREFIX')))
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
Multiplex: replace --sample_id with --experiment_id ID and supply --demux_samplesheet.
POD5:     --basecall --pod5 FILE_OR_DIRECTORY --sample_id ID (or POD5 manifest)
          steps.basecall.model and steps.basecall.modified_models in params YAML
Retries:   --max_retries 2 (two retries after the initial attempt, for all processes)
Resources: --basecall_cpus 4 --basecall_memory '16 GB' (per GPU chunk)
GPU:      --gpu_queue (Slurm), --aws_gpu_queue (AWS), or --basecall_device (local)
          --genome hg38 --fasta reference.fa (or --reference_bundle bundle.json)
          --targets_bed targets.bed
          --enrichment_bed enrichment.bed --image_manifest images.json
Tier:     --primary (default), --secondary, or --tertiary
Optional: --demux_samplesheet demux.csv --no-trim-adapter --sequencing_kit KIT_NAME
          --callers nasvar,sniffles --basecall_model sup|hac|fast
QC:       --disable-qc true skips comprehensive QC, retaining CpG bedMethyl.
Demux sheet: local CSV path or s3://bucket/key.csv.
             experiment_id,kit,barcode,alias (extra sequencer columns accepted).
Demux always trims barcodes. Adapter/primer trimming defaults on; --no-trim-adapter disables it.
Trimming requires --sequencing_kit or the demux sheet's kit column.
Caller GPUs: Clair3/DeepSomatic automatic with a configured GPU queue/device; ClairS-TO defaults to CPU.
             --clair3_gpu false / --clairsto_gpu false / --deepsomatic_gpu false force CPU independently.
DeepSomatic: hg38 tertiary default; ONT_TUMOR_ONLY, targets_bed, default PoN filtering.
Consensus: automatic NASVAR-query PASS agreement when DeepSomatic and ClairS-TO are both selected.
Summary:   per-sample offline Quarto HTML in every tier; requires a pinned summary image.
AWS paths: --run_id ID appends ID to Terraform work/results prefixes; -work-dir and --outdir override.
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
        WorkflowPlan.validateAdapterTrimming(params as Map)
        def plan = WorkflowPlan.resolve(params as Map, bundle)
        def imageLock = WorkflowPlan.readJson(projectPath.call(params.image_manifest))
        def neededImages = (['preprocess','classy','summary'] + plan.callers).unique()
        if (plan.callers.intersect(['clair3','clairsto','deepsomatic']) && !neededImages.contains('bcftools')) neededImages += 'bcftools'
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
            assets[name] = (plan.callers.contains('nasvar') || (plan.callers.containsAll(['deepsomatic','clairsto']) && name in ['gff','config','reference'])) ? assetPath.call(bundle.nasvar?.get(name)) : []
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
        if (plan.callers.contains('deepsomatic')) WorkflowPlan.validateDeepsomatic(params as Map, workflow.profile)
        if (plan.callers.contains('clair3')) WorkflowPlan.validateClair3Gpu(params as Map, workflow.profile)
        if (plan.callers.contains('clairsto')) WorkflowPlan.validateClairstoGpu(params as Map, workflow.profile)
        demux = params.demux_samplesheet ? Channel.fromPath(params.demux_samplesheet, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([])
        sampleRows = params.input ? Channel.fromPath(params.input, checkIfExists:true).splitCsv(header:true, strip:true).collect(flat:false) : Channel.value([[sample:Basecalling.directIdentity(params as Map), run:Basecalling.directIdentity(params as Map), bam:params.bam, pod5:params.pod5]])
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
        def parameterNames = ['run_id','max_retries','basecall','pod5','basecall_cpus','basecall_memory','basecall_tasks','basecall_max_forks','basecall_device','bam','experiment_id','sample_id','input','demux_samplesheet','no_trim_adapter','sequencing_kit','genome','reference_bundle','targets_bed','enrichment_bed','callers','max_cpus','max_memory','max_time','qdnaseq_binsize','delly_bin_size','ichor_bin_size','deepsomatic_gpu','deepsomatic_cpus','deepsomatic_memory','clair3_gpu','clairsto_gpu','clairsto_gpu_threads','basecall_model','disable_qc']
        provenance.parameters = parameterNames.collectEntries { key -> [(key):params[key]] }
        provenance.parameters.basecall_assets = params.steps?.basecall
        provenance.parameters.no_trim_adapter = !WorkflowPlan.adapterTrimming(params as Map)
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
