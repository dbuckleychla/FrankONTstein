#!/usr/bin/env python3
"""Create mock executables for DAG contract tests, never scientific validation."""
from pathlib import Path
import sys

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
script = '''#!/usr/bin/env python3
import sys
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
def value(flag): return args[args.index(flag)+1]
def touch(path):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text("contract-test-only\\n")
if any(x in args for x in ['--version','-v']):
 print(name+' version contract-test');sys.exit(0)
if name=='bcftools': touch(value('-o'))
elif name=='run_clairs_to':
 for f in ['snv.vcf.gz','indel.vcf.gz']:touch(str(Path(value('-o'))/f))
elif name=='sniffles': touch(value('--vcf'))
elif name=='severus': touch('somatic_SVs/severus_somatic.vcf')
elif name=='stellerator':
 touch(value('--output-vcf'));touch('fusion.tsv');touch('fusion.fasta.gz')
elif name=='call_qdnaseq.R':
 for suffix in ['calls.vcf','calls.bed','segs.vcf','segs.bed','segs.seg','cov.png','noise_plot.png','isobar_plot.png']:
  touch(value('--prefix')+'_'+suffix)
elif name=='R': print('R version contract-test')
else: raise SystemExit('Unknown contract mock '+name)
'''
for tool in ['bcftools','run_clairs_to','sniffles','severus','stellerator','call_qdnaseq.R','R']:
    path=out/tool;path.write_text(script);path.chmod(0o755)
