class RunStatus {
    static List summarize(List samples, List callers, String trace) {
        def aliases = [ALIGN:'alignment', CLASSY_COMBINED:'methylation', NASVAR:'nasvar', CLAIR3:'clair3',
            CLAIRS_TO_CALL:'clairsto', BCFTOOLS_MPILEUP:'bcftools', BCFTOOLS_CALL:'bcftools',
            SNIFFLES_CALL:'sniffles', SEVERUS_TUMOR_UNPHASED:'severus', STELLERATOR:'stellerator',
            QDNASEQ_CALL:'qdnaseq', DELLY:'delly', SUBCHROM:'subchrom', ICHORCNA:'ichorcna']
        def outcomes = [:]
        def lines = trace.readLines()
        if (lines) {
            def header = lines[0].split('\t') as List
            lines.drop(1).each { line ->
                def values = line.split('\t', -1)
                def name = values[header.indexOf('name')]
                def status = values[header.indexOf('status')]
                def match = name =~ /(?:^|:)([A-Z_0-9]+) \(([^:()]+)(?::([^()]+))?\)$/
                if (match.find()) {
                    def process = match.group(1)
                    def sample = match.group(2)
                    def analysis = process == 'PUBLISH_ARTIFACT' ? match.group(3) : process == 'FILTER_VARIANTS' ? match.group(3)?.tokenize(':')?.getAt(0) : aliases[process]
                    if (analysis) {
                        def key = [sample,analysis]
                        if (status == 'FAILED') outcomes[key] = 'failed'
                        else if (status in ['COMPLETED','CACHED'] && process in ['PUBLISH_ARTIFACT','ALIGN'] && outcomes[key] != 'failed') outcomes[key] = 'completed'
                    }
                }
            }
        }
        samples.collectMany { sample ->
            (['alignment','methylation'] + callers).collect { analysis ->
                [sample:sample, analysis:analysis, status:outcomes[[sample,analysis]] ?: 'not_completed', files:[]]
            }
        }
    }
}
