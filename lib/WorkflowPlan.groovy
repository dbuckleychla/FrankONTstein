import groovy.json.JsonSlurper

class WorkflowPlan {
    static void validateRunId(Map params, boolean usesPrefixes) {
        if (usesPrefixes && !params.run_id) throw new IllegalArgumentException('AWS prefix defaults require --run_id (specified on the Nextflow invocation)')
        if (params.run_id != null && !(params.run_id.toString() ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
            throw new IllegalArgumentException('--run_id must start with a letter/digit and contain only letters, digits, dots, underscores or hyphens')
    }

    static boolean clair3Gpu(Map p, String profiles) {
        def value = p.clair3_gpu == null ? 'auto' : p.clair3_gpu.toString()
        if (!(value in ['auto', 'true', 'false']))
            throw new IllegalArgumentException('--clair3_gpu must be auto, true or false')
        def selected = profiles.tokenize(',')
        def configured = selected.contains('aws') ? p.aws_gpu_queue : selected.contains('slurm') ? p.gpu_queue : p.basecall_device
        return value == 'auto' ? configured != null && configured.toString() != '' : value.toBoolean()
    }

    static void validateClair3Gpu(Map p, String profiles) {
        if (!clair3Gpu(p, profiles)) return
        def selected = profiles.tokenize(',')
        if (selected.contains('aws')) {
            if (!p.aws_gpu_queue) throw new IllegalArgumentException('Clair3 GPU execution requires --aws_gpu_queue')
        } else if (selected.contains('slurm')) {
            if (!p.gpu_queue || !selected.contains('apptainer'))
                throw new IllegalArgumentException('Clair3 GPU execution requires --gpu_queue and -profile slurm,apptainer')
        } else if (!selected.contains('docker') || !(p.basecall_device?.toString() ==~ /(?:[0-9]+|GPU-[a-fA-F0-9-]+)/)) {
            throw new IllegalArgumentException('Local Clair3 GPU execution requires -profile local,docker and --basecall_device NVIDIA_INDEX_OR_UUID')
        }
    }

    static boolean clairstoGpu(Map p, String profiles) {
        clair3Gpu(p + [clair3_gpu:p.clairsto_gpu == null ? false : p.clairsto_gpu], profiles)
    }

    static void validateClairstoGpu(Map p, String profiles) {
        try {
            validateClair3Gpu(p + [clair3_gpu:p.clairsto_gpu == null ? false : p.clairsto_gpu], profiles)
        } catch (IllegalArgumentException fault) {
            throw new IllegalArgumentException(fault.message.replace('Clair3', 'ClairS-TO').replace('clair3_gpu', 'clairsto_gpu'))
        }
        if (clairstoGpu(p, profiles) && !(p.clairsto_gpu_threads?.toString() ==~ /[1-9][0-9]*/))
            throw new IllegalArgumentException('--clairsto_gpu_threads must be a positive integer')
    }

    static boolean deepsomaticGpu(Map p, String profiles) {
        clair3Gpu(p + [clair3_gpu:p.deepsomatic_gpu == null ? 'auto' : p.deepsomatic_gpu], profiles)
    }

    static void validateDeepsomatic(Map p, String profiles) {
        try {
            validateClair3Gpu(p + [clair3_gpu:p.deepsomatic_gpu == null ? 'auto' : p.deepsomatic_gpu], profiles)
        } catch (IllegalArgumentException fault) {
            throw new IllegalArgumentException(fault.message.replace('Clair3', 'DeepSomatic').replace('clair3_gpu', 'deepsomatic_gpu'))
        }
        if (!(p.deepsomatic_cpus?.toString() ==~ /[1-9][0-9]*/))
            throw new IllegalArgumentException('--deepsomatic_cpus must be a positive integer')
        if ((p.deepsomatic_memory as nextflow.util.MemoryUnit).toBytes() <= 0)
            throw new IllegalArgumentException('--deepsomatic_memory must be positive')
    }

    static void validateAws(Map params, java.nio.file.Path workDir) {
        def missing = ['aws_queue', 'aws_region', 'aws_job_role'].findAll { !params[it] }.collect { "--${it}" }
        if (workDir.toUri().scheme != 's3') missing.add('-work-dir s3://... (or FRANKONTSTEIN_WORK_PREFIX + --run_id)')
        if (missing) throw new IllegalArgumentException("AWS requires: ${missing.join(', ')}")
    }

    static String clair3Model(Object value) {
        def mode = (value ?: 'sup').toString()
        if (!(mode in ['sup', 'hac', 'fast']))
            throw new IllegalArgumentException('--basecall_model must be sup, hac or fast')
        return "/opt/models/r1041_e82_400bps_${mode == 'sup' ? 'sup' : 'hac'}_v500"
    }

    static Map reference(Map p, Map legacy, String projectDir) {
        if (legacy && (p.fasta || p.fai || (p.steps ?: [:]).keySet().any { !(it in ['basecall', 'clair3']) }))
            throw new IllegalArgumentException('Use reference_bundle or shared fasta/fai/steps, not both')
        def b = legacy ? new LinkedHashMap(legacy) : [schema_version:1,
            id:p.reference_id ?: "${genome(p.genome)}-local", genome:genome(p.genome),
            fasta:p.fasta, fai:p.fai ?: (p.fasta ? "${p.fasta}.fai" : null)]
        if (!b.fasta || !b.fai) throw new IllegalArgumentException('Reference requires fasta and fai')
        def steps = p.steps ?: [:]
        b.nasvar = new LinkedHashMap(legacy ? (legacy.nasvar ?: [:]) : (steps.nasvar ?: [:]))
        if (!legacy) {
            b.models = [clairsto:steps.clairsto?.model]
            b.callers = [fusion_list:steps.stellerator?.fusion_list, delly_map:steps.delly?.map,
                subchrom_panel:steps.subchrom?.panel]
            ['gc','map','centromeres','panel','seqinfo'].each { key ->
                b.callers["ichor_${key}"] = steps.ichorcna?.get(key)
            }
        }
        b.models = new LinkedHashMap(b.models ?: [:])
        if (steps.clair3?.model) {
            def name = steps.clair3.model.toString().tokenize('/').last()
            def mode = (p.basecall_model ?: 'sup').toString()
            if (!(mode in ['sup', 'hac']) || !(name ==~ /r1041_e82_400bps_${mode}_v[0-9]+_with_mv/))
                throw new IllegalArgumentException('steps.clair3.model must be a canonical SUP/HAC with_mv model matching --basecall_model')
        }
        b.models.clair3 = steps.clair3?.model ?: clair3Model(p.basecall_model)
        def build = genome(b.genome)
        def dir = "${projectDir}/vendor/nasvar/config"
        if (!b.nasvar.reference) b.nasvar.reference = "${dir}/${build == 'hg38' ? 'GRCh38_reference.json' : 'T2T-CHM13v2.0_reference.json'}"
        if (!b.nasvar.config)
            b.nasvar.config = "${dir}/${build == 'hg38' ? 'peds_leukemia_config.GRCh38.json' : 'peds_leukemia_config.json'}"

        b
    }
    static final List CALLERS = ['nasvar','bcftools','clair3','clairsto','deepsomatic','sniffles','severus','stellerator','qdnaseq','delly','subchrom','ichorcna']
    static String genome(Object value) {
        def aliases = ['hg38':'hg38', 'grch38':'hg38', 'hs1':'hs1', 'chm13':'hs1', 't2t':'hs1']
        def result = aliases[value?.toString()?.toLowerCase()]
        if (!result) throw new IllegalArgumentException('Genome must be hg38/GRCh38 or hs1/CHM13')
        result
    }
    static boolean qcDisabled(Map p) {
        def value = p.containsKey('disableQc') ? p.disableQc : (p.containsKey('disable-qc') ? p['disable-qc'] : (p.disable_qc ?: false))
        if (value instanceof Boolean) return value
        if (value instanceof String && value in ['true','false']) return value.toBoolean()
        throw new IllegalArgumentException('--disable-qc must be true or false')
    }

    static boolean adapterTrimming(Map p) {
        if (p.containsKey('trim')) throw new IllegalArgumentException('--trim has been removed; adapter trimming is on by default. Use --no-trim-adapter to disable it')
        def disabled = p.containsKey('noTrimAdapter') ? p.noTrimAdapter : (p.containsKey('no-trim-adapter') ? p['no-trim-adapter'] : (p.no_trim_adapter == null ? false : p.no_trim_adapter))
        if (!(disabled instanceof Boolean) && !(disabled in ['true','false']))
            throw new IllegalArgumentException('--no-trim-adapter must be true or false')
        return !disabled.toString().toBoolean()
    }

    static void validateAdapterTrimming(Map p) {
        if (adapterTrimming(p) && !p.demux_samplesheet && !p.sequencing_kit?.toString()?.trim())
            throw new IllegalArgumentException('Default adapter trimming requires --sequencing_kit or --demux_samplesheet; use --no-trim-adapter to disable it')
    }

    static Map resolve(Map p, Map bundle) {
        p = new LinkedHashMap(p)
        p.disable_qc = qcDisabled(p)
        ['primary','secondary','tertiary','no_trim_adapter','disable_qc'].each { key ->
            if (p[key] instanceof String && p[key] in ['true','false']) p[key] = p[key].toBoolean()
        }
        ['primary','secondary','tertiary','no_trim_adapter','disable_qc'].each { key ->
            if (p[key] != null && !(p[key] instanceof Boolean)) throw new IllegalArgumentException("${key} must be boolean")
        }
        if (p.sequencing_kit) identifier(p.sequencing_kit.toString())
        def flags = ['primary','secondary','tertiary'].findAll { p[it] == true }
        if (flags.size() > 1) throw new IllegalArgumentException('Choose only one analysis tier')
        def tier = flags ? flags[0] : 'primary'
        def build = genome(p.genome ?: bundle.genome)
        if (build != genome(bundle.genome)) throw new IllegalArgumentException('Reference bundle genome mismatch')
        if (bundle.schema_version != 1 || !bundle.id) throw new IllegalArgumentException('Reference bundle requires schema_version=1 and id')
        def allowed = tier == 'primary' ? [] : tier == 'secondary' ? ['nasvar'] : CALLERS
        def incompatible = build == 'hs1' ? ['qdnaseq','subchrom','ichorcna','deepsomatic'] : []
        def explicit = p.callers != null
        def requested = explicit ? p.callers.toString().split(',').collect { it.trim() }.unique() : allowed
        if (explicit && !p.callers.toString().trim()) throw new IllegalArgumentException('--callers cannot be empty')
        requested.each {
            if (!allowed.contains(it)) throw new IllegalArgumentException("Caller ${it} is not available in ${tier}")
            if (explicit && incompatible.contains(it)) throw new IllegalArgumentException("Caller ${it} does not support ${build}")
        }
        def skipped = requested.findAll { incompatible.contains(it) }.collect { [caller:it, reason:it == 'deepsomatic' ? 'DeepSomatic initial scope is hg38 only' : "unsupported reference ${build}"] }
        if (p.disable_qc == true) skipped += [caller:'qc', reason:'disabled by --disable_qc']
        def selected = requested - incompatible
        // SubChrom consumes germline allele frequencies from Clair3.
        if (selected.contains('subchrom') && !selected.contains('clair3')) selected += 'clair3'
        [tier:tier, genome:build, callers:selected, skipped:skipped, reference_id:bundle.id]
    }
    static void identifier(String value) {
        if (!value || !(value ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
            throw new IllegalArgumentException("Unsafe or empty identifier: ${value}")
    }
    /** Normalize the sequencer export at the input boundary; optional columns do not route reads. */
    static List demuxRows(List rows) {
        if (!rows) throw new IllegalArgumentException('Demux sheet is empty')
        rows.collect { row ->
            ['experiment_id','kit','barcode','alias'].each { column ->
                if (!(row[column] instanceof CharSequence) || !row[column].toString().trim())
                    throw new IllegalArgumentException("Demux sheet requires non-empty ${column}; expected sequencer columns experiment_id,kit,barcode,alias")
                identifier(row[column].toString().trim())
            }
            [run:row.experiment_id.toString().trim(), kit:row.kit.toString().trim(),
             barcode:row.barcode.toString().trim(), sample:row.alias.toString().trim()]
        }
    }

    static List samples(List rows, List mapping, boolean demux, String kit = null) {
        if (!rows) throw new IllegalArgumentException('Input manifest is empty')
        def seen = []
        rows.each { row ->
            identifier(row.sample as String)
            identifier(row.run as String)
            if (!row.bam || seen.contains(row.bam)) throw new IllegalArgumentException('Missing or duplicate BAM in manifest')
            seen += row.bam
        }
        if (demux) {
            if (!mapping) throw new IllegalArgumentException('Demux sheet is empty')
            def keys = []; def ids = []
            mapping.each { row ->
                ['run','sample','kit','barcode'].each { identifier(row[it] as String) }
                if (keys.contains([row.run,row.barcode]) || ids.contains(row.sample))
                    throw new IllegalArgumentException('Duplicate demux barcode mapping or sample identity')
                keys << [row.run,row.barcode]; ids << row.sample
            }
            if ((rows*.run as Set) != (mapping*.run as Set)) throw new IllegalArgumentException('Demux experiment_id values and input run IDs must match')
            return rows.groupBy { it.run }.collect { run, chunks ->
                def mappings = mapping.findAll { it.run == run }
                if (mappings*.kit.unique().size() != 1) throw new IllegalArgumentException('Each run must have one barcode kit')
                [[id:run, kit:mappings[0].kit, mappings:mappings], chunks*.bam]
            }
        }
        rows.groupBy { it.sample }.collect { sample, chunks -> [[id:sample, kit:kit], chunks*.bam] }
    }
    static Map readJson(path) { new JsonSlurper().parseText(path.text) as Map }
}
