/* Adapted from oncoseq's CLASSY_COMBINED (MIT). Bundle models in the selected
 * image; its immutable digest and model manifest are part of reference provenance.
 * Collect all classifier products without requiring a cfDNA-specific plot.
 */
process CLASSY_COMBINED {
    tag "${meta.id}"
    container { params.images.classy }
    input:
    tuple val(meta), path(bam), path(bai), val(genome), path(fasta), path(fai)
    output:
    tuple val(meta), path('classy'), emit: results
    path 'versions.yml', emit: versions
    script:
    def build = genome == 'hs1' ? 't2t' : genome
    """
    mkdir classy
    classy combined -i '${bam}' -o 'classy/${meta.id}_combined_classification.json' \
      --sample '${meta.id}' --reference '${fasta}' --use-pileup --motif CpG:CG \
      --genome '${build}' --pileup-threads ${task.cpus}
    test -s 'classy/${meta.id}_combined_classification.json'
    classy --version > versions.yml 2>&1
    modkit --version >> versions.yml
    """
    stub:
    """
    mkdir classy
    printf '{"stub":true}\n' > 'classy/${meta.id}_combined_classification.json'
    printf '<svg xmlns="http://www.w3.org/2000/svg"/>\n' > classy/classification.svg
    printf 'classy: stub\n' > versions.yml
    """
}
