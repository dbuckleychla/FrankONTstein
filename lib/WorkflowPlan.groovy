import groovy.json.JsonSlurper

class WorkflowPlan {
    static void validateAws(Map params, java.nio.file.Path workDir) {
        def missing = ['aws_queue', 'aws_region', 'aws_job_role'].findAll { !params[it] }.collect { "--${it}" }
        if (workDir.toUri().scheme != 's3') missing.add('-work-dir s3://... (or FRANKONTSTEIN_WORK_DIR)')
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
    static final List CALLERS = ['nasvar','bcftools','clair3','clairsto','sniffles','severus','stellerator','qdnaseq','delly','subchrom','ichorcna']
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

    static Map resolve(Map p, Map bundle) {
        p = new LinkedHashMap(p)
        p.disable_qc = qcDisabled(p)
        ['primary','secondary','tertiary','trim','disable_qc'].each { key ->
            if (p[key] instanceof String && p[key] in ['true','false']) p[key] = p[key].toBoolean()
        }
        ['primary','secondary','tertiary','trim','disable_qc'].each { key ->
            if (p[key] != null && !(p[key] instanceof Boolean)) throw new IllegalArgumentException("${key} must be boolean")
        }
        if (p.trim == true && !p.demux_samplesheet && !p.sequencing_kit?.toString()?.trim())
            throw new IllegalArgumentException('--trim requires --sequencing_kit, or a --demux_samplesheet with a kit for every run')
        if (p.sequencing_kit) identifier(p.sequencing_kit.toString())
        def flags = ['primary','secondary','tertiary'].findAll { p[it] == true }
        if (flags.size() > 1) throw new IllegalArgumentException('Choose only one analysis tier')
        def tier = flags ? flags[0] : 'primary'
        def build = genome(p.genome ?: bundle.genome)
        if (build != genome(bundle.genome)) throw new IllegalArgumentException('Reference bundle genome mismatch')
        if (bundle.schema_version != 1 || !bundle.id) throw new IllegalArgumentException('Reference bundle requires schema_version=1 and id')
        def allowed = tier == 'primary' ? [] : tier == 'secondary' ? ['nasvar'] : CALLERS
        def incompatible = build == 'hs1' ? ['qdnaseq','subchrom','ichorcna'] : []
        def explicit = p.callers != null
        def requested = explicit ? p.callers.toString().split(',').collect { it.trim() }.unique() : allowed
        if (explicit && !p.callers.toString().trim()) throw new IllegalArgumentException('--callers cannot be empty')
        requested.each {
            if (!allowed.contains(it)) throw new IllegalArgumentException("Caller ${it} is not available in ${tier}")
            if (explicit && incompatible.contains(it)) throw new IllegalArgumentException("Caller ${it} does not support ${build}")
        }
        def skipped = requested.findAll { incompatible.contains(it) }.collect { [caller:it, reason:"unsupported reference ${build}"] }
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
