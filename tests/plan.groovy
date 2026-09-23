def loader = new GroovyClassLoader(getClass().classLoader)
def planner = loader.parseClass(new File('lib/WorkflowPlan.groovy'))
def hg38 = [schema_version:1, id:'hg38-test', genome:'GRCh38']
def hs1 = [schema_version:1, id:'hs1-test', genome:'CHM13']
def rejects = { Closure fn ->
    boolean rejected = false
    try { fn() } catch (IllegalArgumentException expected) { rejected = true }
    assert rejected
}
assert planner.resolve([:],hg38).tier == 'primary'
assert planner.resolve([secondary:true],hg38).callers == ['nasvar']
assert planner.resolve([tertiary:true],hg38).callers.size() == 11
assert planner.resolve([tertiary:true],hs1).skipped*.caller == ['qdnaseq','subchrom','ichorcna']
assert planner.resolve([tertiary:true,callers:'subchrom'],hg38).callers == ['subchrom','clair3']
assert planner.resolve([tertiary:true,callers:'nasvar,sniffles'],hs1).callers == ['nasvar','sniffles']
rejects { planner.resolve([primary:true,secondary:true],hg38) }
rejects { planner.resolve([secondary:true,tertiary:true],hg38) }
rejects { planner.resolve([callers:'nasvar'],hg38) }
rejects { planner.resolve([secondary:true,callers:'sniffles'],hg38) }
rejects { planner.resolve([tertiary:true,callers:'qdnaseq'],hs1) }
rejects { planner.resolve([genome:'hg19'],hg38) }
rejects { planner.resolve([genome:'CHM13'],hg38) }
rejects { planner.identifier('sample; rm -rf x') }
println '13 tier/reference/identifier assertions passed'
def rows = [[sample:'s1',run:'r1',bam:'a.bam'],[sample:'s1',run:'r1',bam:'b.bam']]
assert planner.samples(rows,[],false)[0][1] == ['a.bam','b.bam']
rejects { planner.samples(rows + rows,[],false) }
def mapping = [[sample:'s2',run:'r1',kit:'kit',barcode:'barcode01']]
assert planner.samples(rows,mapping,true)[0][0].mappings[0].sample == 's2'
rejects { planner.samples(rows,mapping*2,true) }
rejects { planner.samples(rows,[],true) }
rejects { planner.samples(rows,[[sample:'s2',run:'r2',kit:'kit',barcode:'barcode01']],true) }
rejects { planner.samples([[sample:'bad name',run:'r',bam:'x']],[],false) }
println '7 sample manifest assertions passed'
def statusClass = loader.parseClass(new File('lib/RunStatus.groovy'))
def summary = statusClass.summarize(['s1'],['nasvar'], 'name\tstatus\nPRIMARY:ALIGN (s1)\tCOMPLETED\nSECONDARY:NASVAR (s1:secondary)\tFAILED\n')
assert summary.find { it.analysis == 'alignment' }.status == 'completed'
assert summary.find { it.analysis == 'nasvar' }.status == 'failed'
assert summary.find { it.analysis == 'methylation' }.status == 'not_completed'
println '3 failed-run reporting assertions passed'
def shared = [genome:'GRCh38', fasta:'/ref/hg38.fa', steps:[nasvar:[:]]]
def normalized = planner.reference(shared, [:], '/project')
assert normalized.fai == '/ref/hg38.fa.fai'
assert normalized.nasvar.reference.endsWith('/GRCh38_reference.json')
assert normalized.nasvar.config.endsWith('/peds_leukemia_config.GRCh38.json')
def chm = planner.reference(shared + [genome:'CHM13'], [:], '/project')
assert chm.nasvar.reference.endsWith('/T2T-CHM13v2.0_reference.json')
assert chm.nasvar.config.endsWith('/peds_leukemia_config.json')
assert planner.reference([genome:'hg38',fasta:'ref.fa'],[:],'/project').nasvar.config.endsWith('/peds_leukemia_config.GRCh38.json')
rejects { planner.reference(shared, hg38 + [fasta:'ref.fa',fai:'ref.fa.fai'], '/project') }
assert planner.reference(shared + [steps:[nasvar:[config:'custom.json']]], [:], '/project').nasvar.config == 'custom.json'
println '8 shared-input and NASVAR default assertions passed'
assert planner.resolve([primary:'false',secondary:'true'],hg38).tier == 'secondary'
assert planner.resolve([primary:'false',secondary:'false',tertiary:'true'],hg38).tier == 'tertiary'
rejects { planner.resolve([primary:'yes'],hg38) }
println '3 strict-parser CLI boolean assertions passed'
rejects { planner.resolve([trim:true], hg38) }
rejects { planner.resolve([trim:'true',sequencing_kit:'  '], hg38) }
assert planner.resolve([trim:false], hg38).tier == 'primary'
assert planner.resolve([trim:'false'], hg38).tier == 'primary'
assert planner.resolve([trim:true,sequencing_kit:'SQK-LSK114'], hg38).tier == 'primary'
assert planner.resolve([trim:true,demux_samplesheet:'demux.csv'], hg38).tier == 'primary'
rejects { planner.samples(rows, [[sample:'s2',run:'r1',kit:'',barcode:'barcode01']], true) }
println '7 trimming kit preflight assertions passed'

assert planner.clair3Model(null) == '/opt/models/r1041_e82_400bps_sup_v500'
assert planner.clair3Model('sup') == '/opt/models/r1041_e82_400bps_sup_v500'
assert planner.clair3Model('hac') == '/opt/models/r1041_e82_400bps_hac_v500'
assert planner.clair3Model('fast') == '/opt/models/r1041_e82_400bps_hac_v500'
try { planner.clair3Model('typo'); assert false } catch (IllegalArgumentException expected) { }
