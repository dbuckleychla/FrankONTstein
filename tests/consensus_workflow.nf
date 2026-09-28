include { SOMATIC_CONSENSUS } from '../modules/local/consensus/main'
include { SAMPLE_SUMMARY } from '../modules/local/summary/main'

workflow {
    def root = "${params.test_root}/tests/fixtures"
    calls = Channel.of(tuple([id:'sample1'],[file("${root}/stub.bam")],[file("${root}/stub.bam")]),
                       tuple([id:'sample2'],[file("${root}/stub.bam")],[file("${root}/stub.bam")]))
    SOMATIC_CONSENSUS(calls, Channel.value(tuple(file("${root}/reference.fa"),file("${root}/reference.fa.fai"),true)), file(root))
    summaries = SOMATIC_CONSENSUS.out.results.map { m,f ->
        assert f.size() == 5
        assert f.every { it.name.startsWith(m.id + '.') }
        tuple(m,['consensus'],f.findAll { it.name.endsWith('.json') })
    }
    SAMPLE_SUMMARY(summaries, [plan:[tier:'tertiary',genome:'hg38',callers:['deepsomatic','clairsto']]],file("${params.test_root}/assets/summary/template.qmd"))
    SAMPLE_SUMMARY.out.results.map { m,h,j ->
        assert h.name == "${m.id}.summary.html"
        assert j.name == "${m.id}.summary.json"
        m.id
    }.collect().map { ids -> assert ids.toSet() == ['sample1','sample2'].toSet(); true }.view()
}
