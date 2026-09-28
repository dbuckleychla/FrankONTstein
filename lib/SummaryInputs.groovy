/** Select only small report inputs from work artifacts, never stage BAMs or full result directories. */
class SummaryInputs {
    static List select(Map meta, String analysis, files) {
        def paths = files instanceof List ? files : [files]
        def selected = []
        paths.each { p ->
            if (analysis == 'methylation' && p.name == 'classy') {
                ["${meta.id}_combined_classification.json", "${meta.id}_combined_classification_combined_top_calls.tsv"].each { name ->
                    def f = p.resolve(name)
                    if (f.exists()) selected.add(f)
                }
            } else if (analysis == 'nasvar' && p.name == 'nasvar') {
                ["${meta.id}.result.json", "${meta.id}.pipeline_config.json", 'quality_warnings.json'].each { name ->
                    def f = p.resolve(name)
                    if (f.exists()) selected.add(f)
                }
            } else if (analysis == 'qc' && p.name == 'qc') {
                selected.add(p.resolve('metrics.json'))
            } else if (analysis == 'consensus' && p.name == "${meta.id}.consensus.json") {
                selected.add(p)
            } else if (analysis == 'stellerator' && p.name.endsWith('.tsv')) {
                selected.add(p)
            }
        }
        selected
    }
}
