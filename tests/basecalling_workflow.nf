include { DORADO_BASECALL } from '../modules/local/basecall/main'

workflow {
    def fixture = file("${params.test_root}/tests/fixtures/stub.bam")
    def paths = Basecalling.batches([fixture, file("${params.test_root}/tests/fixtures/reference.fa")], 16)
    assert paths.size() == 2
    batches = Channel.fromList(paths.withIndex().collect { batch, index -> tuple([id:'run1'], "batch_${index}", batch) })
    DORADO_BASECALL(batches, fixture, fixture, fixture)
    DORADO_BASECALL.out.bam.groupTuple(by:0).map { meta, ids, bams ->
        assert meta.id == 'run1'
        assert ids.size() == 2
        assert bams.size() == 2
        true
    }.view()
}
