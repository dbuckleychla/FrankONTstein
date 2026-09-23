#!/usr/bin/env python3
"""Real modkit + QC smoke test using the production image lock; no patient data."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser()
p.add_argument('--image-manifest',default='images.lock.json')
p.add_argument('--threads',type=int,default=4)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
images=json.loads(Path(a.image_manifest).read_text())
with tempfile.TemporaryDirectory(prefix='frankontstein-qc-smoke-') as tmp:
    def run(image,command):
        subprocess.run(['docker','run','--rm','--network','none','--entrypoint','/bin/bash',
                        '-v',tmp+':/data','-v',str(root/'bin')+':/workflow/bin:ro',
                        '-w','/data',image,'-euc',command],check=True)
    run(images['preprocess'], '''python3 - <<'PYTHON'
from pathlib import Path
import array
import pysam
Path('reference.fa').write_text('>chr1\\n'+'CG'*1000+'\\n')
pysam.faidx('reference.fa')
Path('enrichment.bed').write_text('chr1\\t0\\t1000\\n')
Path('targets.bed').write_text('chr1\\t200\\t600\\ttarget\\n')
with pysam.AlignmentFile('sample.bam','wb',header={'HD':{'SO':'coordinate'},'SQ':[{'SN':'chr1','LN':2000}]}) as bam:
    for i in range(1000):
        r=pysam.AlignedSegment();r.query_name=f'read{i}';r.query_sequence='CG'*250
        r.flag=0;r.reference_id=0;r.reference_start=0;r.mapping_quality=60;r.cigarstring='500M'
        r.query_qualities=array.array('B',[30]*500)
        r.set_tag('MM','C+m,'+','.join(['0']*250)+';')
        r.set_tag('ML',array.array('B',[240]*250));r.set_tag('MN',500)
        bam.write(r)
pysam.index('sample.bam')
PYTHON''')
    run(images['classy'], f'''modkit pileup sample.bam sample.cpg.bedmethyl.gz --ref reference.fa --cpg --modified-bases 5mC 5hmC --combine-strands --bgzf --threads {a.threads} --log-filepath modkit.log''')
    run(images['preprocess'], f'''python3 -c "import pysam; pysam.tabix_index('sample.cpg.bedmethyl.gz',preset='bed',force=True)"
/workflow/bin/adaptive_qc.py --sample smoke --bam sample.bam --fasta reference.fa --enrichment enrichment.bed --targets targets.bed --bedmethyl sample.cpg.bedmethyl.gz --threads {a.threads}''')
    data=json.loads((Path(tmp)/'qc/metrics.json').read_text())
    assert data['alignment']['counts']['primary_reads']==1000
    assert data['alignment']['alignment_rate']==1
    assert data['methylation']['genome']['combined']['sites']>0
    assert (Path(tmp)/'qc/index.html').exists()
print('Real containerized modkit and QC smoke test passed')
