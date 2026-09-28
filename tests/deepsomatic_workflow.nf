include { DEEPSOMATIC } from '../modules/local/deepsomatic/main'

workflow {
    def root = "${params.test_root}/tests/fixtures"
    def bam = file("${root}/stub.bam")
    def ref = file("${root}/reference.fa")
    def fai = file("${root}/reference.fa.fai")
    def indexFixture = file("${root}/regions.bed")
    samples = Channel.of(tuple([id:'sample1'],bam,indexFixture), tuple([id:'sample2'],bam,indexFixture))
    DEEPSOMATIC(samples, tuple(ref,fai,true), file("${root}/deepsomatic"))
    DEEPSOMATIC.out.results.map { meta, outputs ->
        assert outputs*.name.toSet() == ['somatic.vcf.gz', 'somatic.vcf.gz.tbi', 'logs', 'provenance.json'].toSet()
        meta.id
    }.collect().map { ids ->
        assert ids.toSet() == ['sample1','sample2'].toSet()
        true
    }.view()
}
