#!/usr/bin/env python3
"""Set SM on existing read groups without changing IDs or any read-level tags."""
import argparse
import pysam


def sample_header(path, sample):
    with pysam.AlignmentFile(path,'rb',check_sq=False) as bam:
        header=bam.header.to_dict()
    # No synthetic read-group IDs: RG-free inputs retain their header and callers
    # receive the sample ID through filenames/options and final VCF normalization.
    for group in header.get('RG', []):
        group['SM']=sample
    return str(pysam.AlignmentHeader.from_dict(header))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bam');p.add_argument('sample');a=p.parse_args()
    print(sample_header(a.bam,a.sample),end='')
