/* Adapted from the MIT-licensed oncoseq processes pinned in dependencies.json.
 * Calling behavior retained; sample-named inputs and stdout/stderr outputs added.
 * See vendor/oncoseq/LICENSE for upstream notices. Vendor gitlinks unchanged. */
process BCFTOOLS_CALL {
    // TODO SET CONTAINER TO FIXED VERSION

    container "ghcr.io/chusj-pigu/bcftools:latest"

    label 'process_low'                    // nf-core labels
    label "process_medium_low_cpu"       // Label for mpgi drac cpu alloc
    label "process_medium_low_memory"
    label "process_low_time"

    tag "$meta.id"

    input:
    tuple val(meta),
        path(bcf)

    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta),
        path("*.vcf.gz"),
        emit: vcf
    path "versions.yml",
        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def threads = task.cpus
    """
    source capture_task_logs.sh BCFTOOLS_CALL
    bcftools call \\
        ${args} \\
        --threads ${threads} \\
        ${bcf} \\
        -o ${prefix}_snp.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$( echo \$(bcftools --version 2>&1) | sed 's/^.*bcftools //; s/Using.*\$//' )
    END_VERSIONS
    """
}


process SNIFFLES_CALL {
    // TODO SET CONTAINER TO FIXED VERSION

    container "ghcr.io/chusj-pigu/sniffles:latest"

    label 'process_medium'                    // nf-core labels
    label "process_mid_cpu"                 // Label for mpgi drac cpu alloc
    label "process_medium_mid_memory"         // Label for mpgi drac memory alloc
    label "process_mid_time"

    tag "$meta.id"

    input:
    tuple val(meta),
        path(bam),
        path(bai),
        val(ref_type),
        path(ref_fasta),
        path(ref_fai)

    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta),
        path("*.vcf.gz"),
        emit: vcf
    path "versions.yml",
        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def isPhased = bam.baseName.contains('phased')
    def argsPhased = isPhased ? '--phase' : ''
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def threads = task.cpus
    def tr_bed = ref_type in ["hg38", "GRCh38"] \
        ? "--tandem-repeats /opt/app/human_GRCh38_no_alt_analysis_set.trf.bed" \
        : ref_type in ["hg19", "GRCh37"] \
        ? "--tandem-repeats /opt/app/human_hs37d5.trf.bed" \
        : ""
    """
    source capture_task_logs.sh SNIFFLES_CALL
    sniffles \\
        --input ${bam} \\
        --reference ${ref_fasta} \\
        ${tr_bed} \\
        ${args} \\
        ${argsPhased} \\
        -t ${threads} \\
        --vcf ${prefix}_sv.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        Sniffles2: \$(echo \$(sniffles --version 2>&1) | awk '{print \$NF}' )
    END_VERSIONS
    """
}

process SEVERUS_TUMOR_UNPHASED {
    container "ghcr.io/chusj-pigu/severus:a294582458464a429891218e2be1c8c0db07b199" // TO DO: SET CONTAINER TO FIXED VERSION

    tag "$meta.id"
    label 'process_medium'                    // nf-core labels
    label "process_medium_low_cpu"              // Label for mpgi drac cpu alloc
    label "process_medium_memory"         // Label for mpgi drac memory alloc
    label "process_low_time"

    input:
    tuple val(meta),
        path(bam),
        path(bai),
        val(genome)

    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta),
        path("somatic_SVs/severus_somatic.vcf"),
        emit: vcf
    path "versions.yml",
        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def threads = task.cpus
    def vntr = genome == 'hg38' ? '--vntr-bed /opt/app/Severus/vntrs/human_GRCh38_no_alt_analysis_set.trf.bed' :
        (genome == 'hs1' ? '--vntr-bed /opt/app/Severus/vntrs/chm13.bed' : '')
    def pon  = genome == 'hg38' ? '--PON /opt/app/Severus/pon/PoN_1000G_hg38.tsv.gz' :
        (genome == 'hs1' ? '--PON /opt/app/Severus/pon/PoN_1000G_chm13.tsv.gz' : '')
    """
    source capture_task_logs.sh SEVERUS_TUMOR_UNPHASED
    severus \\
        ${args} \\
        --target-bam ${bam} \\
        --out-dir '.' \\
        -t ${threads} \\
        ${vntr} ${pon}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        Severus: \$(severus -v)
    END_VERSIONS
    """
}

process STELLERATOR {
    // TODO SET CONTAINER TO FIXED VERSION

    container "ghcr.io/chusj-pigu/stellerator:5723fc7c4383bc34f07a9e7c159f9205ce1f8e08"

    label 'process_low'                    // nf-core labels
    label "process_low_cpu"                 // Label for mpgi drac cpu alloc
    label "process_medium_low_memory"         // Label for mpgi drac memory alloc
    label "process_medium_low_time"

    tag "$meta.id"

    input:
    tuple val(meta),
        path(bam),
        path(bai),
        val(refid),
        path(fusion_list)

    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta),
        path("*.vcf"),
        emit: vcf
    tuple val(meta),
        path("*.tsv"),
        emit: tsv
    tuple val(meta),
        path("*.fasta.gz"),
        emit: fasta
    path "versions.yml",
        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args    = task.ext.args ?: ''
    def prefix  = task.ext.prefix ?: "${meta.id}"
    def threads = task.cpus
    def gtf     = "${refid}.ncbiRefSeq.gtf"
    def realtime = params.realtime?.toInteger()
    def support = params.cfdna
        ? 2
        : (realtime != null && realtime <= 6 ? 0 : 3)
    """
    source capture_task_logs.sh STELLERATOR
    stellerator \\
        --bam ${bam} \\
        --annotation /opt/data/${gtf} \\
        --loci ${fusion_list} \\
        --output-vcf ${prefix}.vcf \\
        --min-depth ${support} \\
        --threads ${threads} --verbose

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        Stellerator : \$(stellerator --version | awk '{print \$2}')
    END_VERSIONS
    """
}

process QDNASEQ_CALL {

    //TODO: SET FIXED VERSION WHEN PIPELINE IS STABLE
    container 'ghcr.io/chusj-pigu/qdnaseq:latest'

    label 'medium'
    label 'process_low'
    label 'process_single_cpu'
    label 'process_medium_mid_memory'
    label 'process_low_time'

    tag "$meta.id"

    input:
    tuple val(meta),
        path(bam),
        path(bai),
        val(ref_id)

    output:
    tuple val(meta), path('runtime_logs/*'), emit: logs
    tuple val(meta),
        path("*calls.vcf"),
        emit: call_vcf
    tuple val(meta),
        path("*calls.bed"),
        emit: calls_bed
    tuple val(meta),
        path("*segs.vcf"),
        emit: segs_vcf
    tuple val(meta),
        path("*segs.bed"),
        emit: segs_bed
    tuple val(meta),
        path("*segs.seg"),
        emit: segs_seg
    tuple val(meta),
        path("*cov.png"),
        emit: cov_png
    tuple val(meta),
        path("*noise_plot.png"),
        emit: noise_png
    tuple val(meta),
        path("*isobar_plot.png"),
        emit: isobar_png
    path "versions.yml",
        emit: versions

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    def binsize = params.qdnaseq_binsize
    """
    source capture_task_logs.sh QDNASEQ_CALL
    mkdir sample_input
    ln -s "\$(realpath '${bam}')" 'sample_input/${meta.id}.bam'
    ln -s "\$(realpath '${bai}')" 'sample_input/${meta.id}.bam.bai'
    call_qdnaseq.R \\
        -b 'sample_input/${meta.id}.bam' \\
        -r ${ref_id} \\
        --binsize ${binsize} \\
        --prefix ${prefix}_cnv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        R: \$(R --version | head -n 1 | awk '{print ""\$3}')
        QDNAseq: "\$(echo 'cat(as.character(packageVersion(\"QDNAseq\")))' | R --vanilla --slave)"
    END_VERSIONS
    """
}
