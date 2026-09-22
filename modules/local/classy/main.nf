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
    tuple val(meta), path('methylation'), emit: results
    path 'versions.yml', emit: versions
    script:
    def build = genome == 'hs1' ? 't2t' : genome
    """
    mkdir methylation
    classy combined -i '${bam}' -o 'methylation/${meta.id}_combined_classification.json' \
      --sample '${meta.id}' --reference '${fasta}' --use-pileup --motif CpG:CG \
      --genome '${build}' --pileup-threads ${task.cpus}
    test -s 'methylation/${meta.id}_combined_classification.json'
    classy --version > versions.yml 2>&1
    modkit --version >> versions.yml
    """
    stub:
    """
    mkdir methylation
    printf '{"stub":true}\n' > 'methylation/${meta.id}_combined_classification.json'
    printf '<svg xmlns="http://www.w3.org/2000/svg"/>\n' > methylation/classification.svg
    printf 'classy: stub\n' > versions.yml
    """
}
