import groovy.json.JsonSlurper

class WorkflowPlan {
    static final List CALLERS = ['nasvar','bcftools','clair3','clairsto','sniffles','severus','stellerator','qdnaseq','delly','subchrom','ichorcna']
    static String genome(Object value) {
        def aliases = ['hg38':'hg38', 'grch38':'hg38', 'hs1':'hs1', 'chm13':'hs1', 't2t':'hs1']
        def result = aliases[value?.toString()?.toLowerCase()]
        if (!result) throw new IllegalArgumentException('Genome must be hg38/GRCh38 or hs1/CHM13')
        result
    }
    static Map resolve(Map p, Map bundle) {
        ['primary','secondary','tertiary'].each { key ->
            if (p[key] != null && !(p[key] instanceof Boolean)) throw new IllegalArgumentException("${key} must be boolean")
        }
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
        def selected = requested - incompatible
        // SubChrom consumes germline allele frequencies from Clair3.
        if (selected.contains('subchrom') && !selected.contains('clair3')) selected += 'clair3'
        [tier:tier, genome:build, callers:selected, skipped:skipped, reference_id:bundle.id]
    }
    static void identifier(String value) {
        if (!value || !(value ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
            throw new IllegalArgumentException("Unsafe or empty identifier: ${value}")
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
            if ((rows*.run as Set) != (mapping*.run as Set)) throw new IllegalArgumentException('Demux and input run IDs must match')
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
