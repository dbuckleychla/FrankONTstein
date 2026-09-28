/** Demux may omit a requested barcode in an individual shard, but not a run. */
class Demultiplexing {
    static List sampleBams(Map meta, List files, boolean requireAll = true) {
        meta.mappings.findResults { mapping ->
            def matched = files.findAll { it.name.tokenize('_-.').contains(mapping.barcode) }
            if (!matched && !requireAll) return null
            if (!matched) throw new IllegalArgumentException("${meta.id}/${mapping.barcode}: no demultiplexed BAM across input shards")
            [[id:mapping.sample, kit:meta.kit, input_run:meta.id, require_moves:meta.require_moves ?: false], matched]
        }
    }
}
