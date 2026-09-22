include { PREPARE_BAM; DEMULTIPLEX; TRIM_BAM; ALIGN } from '../modules/local/preprocess/main'
include { VALIDATE_REFERENCE } from '../modules/local/reference/main'
include { CLASSY_COMBINED } from '../modules/local/classy/main'
include { NASVAR } from '../modules/local/nasvar/main'
include { CALLING } from '../subworkflows/local/calling'
include { PUBLISH_ARTIFACT; RESULTS_INDEX; SOFTWARE_VERSIONS } from '../modules/local/report/main'

workflow ADAPTIVE {
    take:
    samples
    ref
    assets
    plan
    resources
    provenance
    statusState
    main:
    VALIDATE_REFERENCE(ref, assets.enrichment, assets.targets, assets.repeats, assets.gff, assets.sites, assets.config, assets.reference, plan.callers.contains('nasvar'))
    PREPARE_BAM(samples)
    versions = PREPARE_BAM.out.versions
    if (params.demux_samplesheet) {
        DEMULTIPLEX(PREPARE_BAM.out.bam)
        versions = versions.mix(DEMULTIPLEX.out.versions)
        reads = DEMULTIPLEX.out.bams.flatMap { meta, outputs ->
            def files = outputs instanceof List ? outputs : [outputs]
            meta.mappings.collect { mapping ->
                def matched = files.findAll { it.name.tokenize('_-.').contains(mapping.barcode) }
                if (matched.size() != 1) error "${meta.id}/${mapping.barcode}: expected one demultiplexed BAM, got ${matched.size()}"
                tuple([id:mapping.sample, kit:meta.kit], matched[0])
            }
        }
    } else {
        reads = PREPARE_BAM.out.bam
    }
    if (params.trim) {
        TRIM_BAM(reads)
        versions = versions.mix(TRIM_BAM.out.versions)
        reads = TRIM_BAM.out.bam
    }
    ALIGN(reads, VALIDATE_REFERENCE.out.reference)
    aligned = ALIGN.out.bam.map { m,b,i ->
        statusState.completed.add([sample:m.id, analysis:'alignment'])
        tuple(m,b,i)
    }
    CLASSY_COMBINED(aligned.combine(VALIDATE_REFERENCE.out.reference).map { m,b,i,f,fi,v -> tuple(m,b,i,plan.genome,f,fi) })
    versions = versions.mix(ALIGN.out.versions, CLASSY_COMBINED.out.versions)
    artifacts = CLASSY_COMBINED.out.results.map { m,f -> tuple(m,'methylation',f) }
    if (plan.callers.contains('nasvar')) {
        NASVAR(aligned, VALIDATE_REFERENCE.out.reference, VALIDATE_REFERENCE.out.assets, plan.tier)
        versions = versions.mix(NASVAR.out.results.map { m,d -> d.resolve('versions.txt') })
        artifacts = artifacts.mix(NASVAR.out.results.map { m,f -> tuple(m,'nasvar',f) })
    }
    if (plan.tier == 'tertiary') {
        CALLING(aligned, VALIDATE_REFERENCE.out.reference, VALIDATE_REFERENCE.out.assets, plan, resources)
        artifacts = artifacts.mix(CALLING.out.results)
        versions = versions.mix(CALLING.out.software)
    }
    PUBLISH_ARTIFACT(artifacts)
    records = PUBLISH_ARTIFACT.out.results.map { m,a,files ->
        statusState.completed.add([sample:m.id, analysis:a])
        def paths = files instanceof List ? files : [files]
        [sample:m.id, analysis:a, status:'completed', files:paths.collect { "${m.id}/${a}/${it.name}" }]
    }.mix(aligned.map { m,b,i -> [sample:m.id, analysis:'alignment', status:'completed', files:["${m.id}/alignment/${b.name}", "${m.id}/alignment/${i.name}"]] })
    SOFTWARE_VERSIONS(versions.collect().map { it.sort { a,b -> a.toString() <=> b.toString() } })
    completeRecords = records.collect().map { rows ->
        def grouped = rows.groupBy { [it.sample, it.analysis] }.collect { key, items ->
            [sample:key[0], analysis:key[1], status:'completed', files:items.collectMany { it.files }.unique().sort()]
        }
        def ids = rows*.sample.unique()
        grouped.sort { a,b -> (a.sample + a.analysis) <=> (b.sample + b.analysis) } + ids.sort().collectMany { id -> plan.skipped.collect { item -> [sample:id, analysis:item.caller, status:'skipped', reason:item.reason, files:[]] } }
    }
    RESULTS_INDEX(completeRecords, provenance, SOFTWARE_VERSIONS.out)

}
