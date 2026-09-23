include { MODKIT_PILEUP; INDEX_BEDMETHYL; SAMPLE_QC; DEMUX_QC } from '../modules/local/qc/main'
include { PREPARE_BAM; DEMULTIPLEX; TRIM_BAM; ALIGN } from '../modules/local/preprocess/main'
include { VALIDATE_REFERENCE } from '../modules/local/reference/main'
include { CLASSY_COMBINED } from '../modules/local/classy/main'
include { NASVAR } from '../modules/local/nasvar/main'
include { CALLING } from '../subworkflows/local/calling'
include { PUBLISH_ARTIFACT; RESULTS_INDEX; SOFTWARE_VERSIONS } from '../modules/local/report/main'

workflow PRIMARY {
    take:
    samples
    ref
    assets
    plan
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
                tuple([id:mapping.sample, kit:meta.kit, input_run:meta.id], matched[0])
            }
        }
    } else {
        reads = PREPARE_BAM.out.bam
    }
    inputQc = PREPARE_BAM.out.qc.map { m,q -> tuple(m.id,[q]) }
    if (params.demux_samplesheet && !WorkflowPlan.qcDisabled(params as Map)) {
        DEMUX_QC(DEMULTIPLEX.out.bams)
        inputQc = inputQc.join(DEMUX_QC.out.qc.map { m,q -> tuple(m.id,q) }).map { id,files,q -> tuple(id,files + [q]) }
    }
    sampleQc = reads.map { m,b -> tuple(m.input_run ?: m.id,m) }.combine(inputQc, by:0).map { id,m,q -> tuple(m.id,q) }
    if (params.trim.toString().toBoolean()) {
        TRIM_BAM(reads)
        versions = versions.mix(TRIM_BAM.out.versions)
        reads = TRIM_BAM.out.bam
        sampleQc = sampleQc.join(TRIM_BAM.out.qc.map { m,q -> tuple(m.id,q) }).map { id,files,q -> tuple(id,files + [q]) }
    }
    ALIGN(reads, VALIDATE_REFERENCE.out.reference)
    aligned = ALIGN.out.bam.map { m,b,i ->
        statusState.completed.add([sample:m.id, analysis:'alignment'])
        tuple(m,b,i)
    }
    CLASSY_COMBINED(aligned.combine(VALIDATE_REFERENCE.out.reference).map { m,b,i,f,fi,v -> tuple(m,b,i,plan.genome,f,fi) })
    versions = versions.mix(ALIGN.out.versions, CLASSY_COMBINED.out.versions)
    MODKIT_PILEUP(aligned, VALIDATE_REFERENCE.out.reference)
    INDEX_BEDMETHYL(MODKIT_PILEUP.out.bed)
    versions = versions.mix(MODKIT_PILEUP.out.versions)
    artifacts = CLASSY_COMBINED.out.results.map { m,f -> tuple(m,'methylation',f) }
        .mix(INDEX_BEDMETHYL.out.bed.join(MODKIT_PILEUP.out.log)
            .map { m,b,i,log -> tuple(m,'bedmethyl',[b,i,log]) })
    qcMetrics = Channel.empty()
    if (!WorkflowPlan.qcDisabled(params as Map)) {
        qcInputs = aligned.join(INDEX_BEDMETHYL.out.bed)
            .map { m,b,i,bed,tbi -> tuple(m.id,m,b,i,bed,tbi) }
            .join(sampleQc).map { id,m,b,i,bed,tbi,files -> tuple(m,b,i,bed,tbi,files) }
        SAMPLE_QC(qcInputs, VALIDATE_REFERENCE.out.reference, assets.enrichment, assets.targets)
        artifacts = artifacts.mix(SAMPLE_QC.out.results.map { m,f -> tuple(m,'qc',f) })
        versions = versions.mix(SAMPLE_QC.out.versions)
        qcMetrics = SAMPLE_QC.out.metrics
    }
    emit:
    bam = aligned
    reference = VALIDATE_REFERENCE.out.reference
    reference_assets = VALIDATE_REFERENCE.out.assets
    results = artifacts
    software = versions
    qc_metrics = qcMetrics
}

workflow SECONDARY {
    take:
    aligned
    reference
    assets
    main:
    NASVAR(aligned, reference, assets, 'secondary')
    emit:
    results = NASVAR.out.results.map { m,f -> tuple(m,'nasvar',f) }
    software = NASVAR.out.results.map { m,d -> d.resolve('versions.txt') }
}

workflow TERTIARY {
    take:
    aligned
    reference
    assets
    plan
    resources
    main:
    CALLING(aligned, reference, assets, plan, resources)
    artifacts = CALLING.out.results
    versions = CALLING.out.software
    if (plan.callers.contains('nasvar')) {
        NASVAR(aligned, reference, assets, 'tertiary')
        artifacts = artifacts.mix(NASVAR.out.results.map { m,f -> tuple(m,'nasvar',f) })
        versions = versions.mix(NASVAR.out.results.map { m,d -> d.resolve('versions.txt') })
    }
    emit:
    results = artifacts
    software = versions
}

workflow REPORTING {
    take:
    aligned
    artifacts
    versions
    plan
    provenance
    statusState
    qcMetrics
    main:
    PUBLISH_ARTIFACT(artifacts)
    records = PUBLISH_ARTIFACT.out.results.map { m,a,files ->
        def paths = files instanceof List ? files : [files]
        def record = [sample:m.id, analysis:a, status:'completed', files:paths.collect { "${m.id}/${a == 'bedmethyl' ? 'methylation' : a}/${it.name}" }]
        statusState.completed.add(record)
        record
    }.mix(aligned.map { m,b,i -> [sample:m.id, analysis:'alignment', status:'completed', files:["${m.id}/alignment/${b.name}", "${m.id}/alignment/${i.name}"]] })
    SOFTWARE_VERSIONS(versions.collect().map { it.sort { a,b -> a.toString() <=> b.toString() } })
    completeRecords = records.collect().map { rows ->
        def grouped = rows.groupBy { [it.sample, it.analysis] }.collect { key, items ->
            [sample:key[0], analysis:key[1], status:'completed', files:items.collectMany { it.files }.unique().sort()]
        }
        def ids = rows.collect { it.sample }.unique()
        grouped.sort { a,b -> (a.sample + a.analysis) <=> (b.sample + b.analysis) } + ids.sort().collectMany { id -> plan.skipped.collect { item -> [sample:id, analysis:item.caller, status:'skipped', reason:item.reason, files:[]] } }
    }
    RESULTS_INDEX(completeRecords, provenance, SOFTWARE_VERSIONS.out, qcMetrics.collect().ifEmpty([]))

}
