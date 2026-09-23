// Explicit invocation avoids nf-test 0.9.2's legacy process-wrapper spread syntax.
include { VALIDATE_REFERENCE } from '../modules/local/reference/main'

workflow {
    def fixtures = "${params.test_root}/tests/fixtures"
    VALIDATE_REFERENCE(
        Channel.value(tuple(file("${fixtures}/reference.fa"), file("${fixtures}/reference.fa.fai"))),
        file("${fixtures}/regions.bed"),
        file("${fixtures}/regions.bed"),
        [], [], [], [], [], false
    )
}
