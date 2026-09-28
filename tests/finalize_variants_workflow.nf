include { FINALIZE_VARIANTS } from '../modules/local/finalize_variants/main'

workflow {
    def root = "${params.test_root}/tests/fixtures"
    inputs = Channel.of(
        tuple([id:'sample1'],'sniffles','sv',file("${root}/stub.bam")),
        tuple([id:'sample2'],'deepsomatic','variants.targets',file("${root}/stub.bam")))
    FINALIZE_VARIANTS(inputs, file("${root}/reference.fa.fai"))
    FINALIZE_VARIANTS.out.results.map { meta, caller, files ->
        assert files.size() == 5
        assert files.every { it.name.startsWith(meta.id+'.') }
        assert files.any { it.name.endsWith('.pass.vcf.gz.tbi') }
        meta.id
    }.collect().map { ids ->
        assert ids.toSet() == ['sample1','sample2'].toSet()
        true
    }.view()
}
