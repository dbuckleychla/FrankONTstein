/** Input and GPU contracts for the optional POD5 entry path. */
class Basecalling {
    static String quote(Object value) {
        "'" + value.toString().replace("'", "'\"'\"'") + "'"
    }

    static boolean enabled(Map p) {
        def value = p.basecall == null ? false : p.basecall
        if (!(value instanceof Boolean) && !(value in ['true','false']))
            throw new IllegalArgumentException('--basecall must be boolean')
        value.toString().toBoolean()
    }

    static int positive(Object value, String name) {
        if (!(value?.toString() ==~ /[1-9][0-9]*/))
            throw new IllegalArgumentException("--${name} must be a positive integer")
        value.toString().toInteger()
    }

    static Map validate(Map p, String executor, String profiles) {
        boolean active = enabled(p)
        if ([p.bam, p.pod5, p.input].count { it } != 1)
            throw new IllegalArgumentException('Choose exactly one of --bam, --pod5 or --input')
        if (!p.input) WorkflowPlan.identifier(p.sample_id as String)
        if (!active) {
            if (p.pod5) throw new IllegalArgumentException('POD5 input requires --basecall')
            return [enabled:false]
        }
        if (p.bam) throw new IllegalArgumentException('--basecall accepts POD5 inputs only')
        def models = p.steps?.basecall
        if (!models?.model || !(models.modified_models instanceof List) || models.modified_models.size() != 1 || !models.modified_models[0])
            throw new IllegalArgumentException('Basecalling requires steps.basecall.model and steps.basecall.modified_models: [combined_5mCG_5hmCG_model_directory]')
        int tasks = positive(p.basecall_tasks, 'basecall_tasks')
        int cpus = positive(p.containsKey('basecall_cpus') ? p.basecall_cpus : 4, 'basecall_cpus')
        def memory = (p.basecall_memory ?: '16 GB') as nextflow.util.MemoryUnit
        if (memory.toBytes() <= 0) throw new IllegalArgumentException('--basecall_memory must be positive')
        if (!(executor in ['local','slurm','awsbatch']))
            throw new IllegalArgumentException("Basecalling does not support executor ${executor}")
        def selected = profiles.tokenize(',')
        if (executor == 'slurm' && (!p.gpu_queue || !selected.contains('slurm') || !selected.contains('apptainer')))
            throw new IllegalArgumentException('Basecalling on Slurm requires -profile slurm,apptainer and --gpu_queue')
        if (executor == 'awsbatch' && (!p.aws_gpu_queue || !selected.contains('aws')))
            throw new IllegalArgumentException('Basecalling on AWS requires -profile aws and --aws_gpu_queue')
        if (executor == 'local' && (!selected.contains('docker') || !(p.basecall_device?.toString() ==~ /(?:[0-9]+|GPU-[a-fA-F0-9-]+)/)))
            throw new IllegalArgumentException('Local basecalling requires -profile local,docker and --basecall_device NVIDIA_INDEX_OR_UUID')
        int forks = p.basecall_max_forks == null ? (executor == 'local' ? 1 : 32) : positive(p.basecall_max_forks, 'basecall_max_forks')
        if (executor == 'local' && forks != 1)
            throw new IllegalArgumentException('Local basecalling requires --basecall_max_forks 1')
        [enabled:true, executor:executor, tasks:tasks, max_forks:forks, cpus:cpus, memory:memory.toString(),
         device:executor == 'local' ? p.basecall_device.toString() : 'scheduler-assigned',
         queue:executor == 'slurm' ? p.gpu_queue : executor == 'awsbatch' ? p.aws_gpu_queue : null]
    }

    static List rows(List rows, boolean active) {
        String field = active ? 'pod5' : 'bam'
        String other = active ? 'bam' : 'pod5'
        rows.collect { row ->
            if (!row[field] || row[other])
                throw new IllegalArgumentException("Every input row must contain ${field} only; mixed BAM/POD5 batches are unsupported")
            def normalized = new LinkedHashMap(row)
            normalized.bam = row[field]
            normalized
        }
    }

    static List batches(List paths, int count) {
        def sorted = paths.sort(false) { a,b -> a.toString() <=> b.toString() }
        if (!sorted) throw new IllegalArgumentException('No direct-child POD5 files found')
        if (sorted.collect { it.toString() }.unique().size() != sorted.size())
            throw new IllegalArgumentException('Duplicate resolved POD5 input')
        def batches = (0..<Math.min(count, sorted.size())).collect { [] }
        sorted.eachWithIndex { path, index -> batches[index % batches.size()] << path }
        batches
    }
}
