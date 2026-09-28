/** Publication categories; logical caller names remain stable for status tracking. */
class OutputLayout {
    static String directory(String analysis) {
        def groups = [germline:['bcftools','clair3'], somatic:['clairsto','deepsomatic','consensus'],
                      structural:['sniffles','severus','stellerator'], CNA:['qdnaseq','delly','subchrom','ichorcna']]
        def group = groups.find { category, callers -> analysis in callers }?.key
        group ? "${group}/${analysis}" : (analysis == 'bedmethyl' ? 'methylation' : analysis)
    }
}
