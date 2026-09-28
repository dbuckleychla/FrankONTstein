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
assert planner.resolve([tertiary:true],hg38).callers.size() == 12
assert planner.resolve([tertiary:true],hs1).skipped*.caller == ['deepsomatic','qdnaseq','subchrom','ichorcna']
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
assert planner.adapterTrimming([:])
assert !planner.adapterTrimming([no_trim_adapter:true])
assert !planner.adapterTrimming([no_trim_adapter:'true'])
assert planner.adapterTrimming([no_trim_adapter:'false'])
rejects { planner.adapterTrimming([trim:true]) }
rejects { planner.adapterTrimming([no_trim_adapter:'yes']) }
rejects { planner.validateAdapterTrimming([:]) }
rejects { planner.validateAdapterTrimming([sequencing_kit:'  ']) }
planner.validateAdapterTrimming([no_trim_adapter:true])
planner.validateAdapterTrimming([sequencing_kit:'SQK-LSK114'])
planner.validateAdapterTrimming([demux_samplesheet:'demux.csv'])
rejects { planner.samples(rows, [[sample:'s2',run:'r1',kit:'',barcode:'barcode01']], true) }
println '7 trimming kit preflight assertions passed'

assert planner.clair3Model(null) == '/opt/models/r1041_e82_400bps_sup_v500'
assert planner.clair3Model('sup') == '/opt/models/r1041_e82_400bps_sup_v500'
assert planner.clair3Model('hac') == '/opt/models/r1041_e82_400bps_hac_v500'
assert planner.clair3Model('fast') == '/opt/models/r1041_e82_400bps_hac_v500'
try { planner.clair3Model('typo'); assert false } catch (IllegalArgumentException expected) { }

assert planner.qcDisabled([:]) == false
assert planner.qcDisabled(['disable-qc':'true',disable_qc:false]) == true
assert planner.qcDisabled([disable_qc:'false']) == false
rejects { planner.qcDisabled(['disable-qc':'yes']) }
assert planner.resolve([primary:true,'disable-qc':true], hg38).skipped.any { it.caller == 'qc' }

assert planner.qcDisabled([disableQc:'true',disable_qc:false]) == true

def qcFailure = statusClass.summarize(['s1'], ['qc','bedmethyl'], 'name\tstatus\nPRIMARY:SAMPLE_QC (s1)\tFAILED\nPRIMARY:INDEX_BEDMETHYL (s1)\tFAILED\n')
assert qcFailure.find { it.analysis == 'qc' }.status == 'failed'
assert qcFailure.find { it.analysis == 'bedmethyl' }.status == 'failed'

def basecaller = loader.parseClass(new File('lib/Basecalling.groovy'))
def raw = [basecall:true,pod5:'raw',sample_id:'s',basecall_tasks:16,basecall_device:'0',steps:[basecall:[model:'model',modified_models:['mod']]]]
assert basecaller.validate(raw, 'local','local,docker').max_forks == 1
assert basecaller.validate(raw + [gpu_queue:'gpu'], 'slurm','slurm,apptainer').max_forks == 32
assert basecaller.validate(raw + [aws_gpu_queue:'gpu'], 'awsbatch','aws').queue == 'gpu'
rejects { basecaller.validate(raw, 'slurm','slurm,apptainer') }
rejects { basecaller.validate(raw, 'awsbatch','aws') }
rejects { basecaller.validate(raw, 'sge','sge') }
rejects { basecaller.validate(raw + [basecall_device:null], 'local','local,docker') }
rejects { basecaller.validate(raw + [basecall_device:'all'], 'local','local,docker') }
rejects { basecaller.validate(raw + [basecall_max_forks:2], 'local','local,docker') }
rejects { basecaller.validate(raw + [basecall_tasks:0], 'local','local,docker') }
rejects { basecaller.validate(raw + [bam:'x.bam'], 'local','local,docker') }
rejects { basecaller.validate(raw + [basecall:false], 'local','local,docker') }
rejects { basecaller.validate(raw + [steps:[:]], 'local','local,docker') }
assert basecaller.validate([bam:'x',sample_id:'s'], 'local','local').enabled == false
assert basecaller.batches(['c','a','b'],2) == [['a','c'],['b']]
assert basecaller.batches(['b','a'],16) == [['a'],['b']]
rejects { basecaller.batches([],16) }
rejects { basecaller.batches(['a','a'],16) }
rejects { basecaller.rows([[bam:'a',pod5:'b']],true) }
rejects { basecaller.rows([[pod5:'a']],false) }
assert basecaller.rows([[sample:'s',run:'r',pod5:'p']],true)[0].bam == 'p'
assert planner.reference([steps:[basecall:[model:'x']]], hg38 + [fasta:'ref.fa',fai:'ref.fa.fai'], '/project').fasta == 'ref.fa'
def rawFailure = statusClass.summarize(['s1','s2'], ['basecalling'], 'name\tstatus\nPRIMARY:DORADO_BASECALL (r:batch_00000001)\tFAILED\n', [r:['s1','s2']])
assert rawFailure.findAll { it.analysis == 'basecalling' }.every { it.status == 'failed' }
println 'Basecalling input, GPU, batching and failure contracts passed'

// Sequencer exports accept arbitrary optional columns; alias, not sample_id, routes outputs.
def sequencer = [[position_id:'p2i-00715-A',flow_cell_id:'PBM29238',sample_id:'other-sequencer-id',experiment_id:'ONT20260917',flow_cell_product_code:'FLO-PRO114M',kit:'SQK-NBD114-24',barcode:'barcode03',alias:'BC3',type:'na',extra:'free text / metadata'],
                 [experiment_id:'ONT20260917',kit:'SQK-NBD114-24',barcode:'barcode04',alias:'BC4']]
def normalizedSheet = planner.demuxRows(sequencer)
assert normalizedSheet == [[run:'ONT20260917',kit:'SQK-NBD114-24',barcode:'barcode03',sample:'BC3'],[run:'ONT20260917',kit:'SQK-NBD114-24',barcode:'barcode04',sample:'BC4']]
def pooled = [[sample:'pool',run:'ONT20260917',bam:'pooled.bam']]
assert planner.samples(pooled, normalizedSheet, true)[0][0].mappings*.sample == ['BC3','BC4']
['experiment_id','kit','barcode','alias'].each { field ->
    def missing = new LinkedHashMap(sequencer[0]); missing.remove(field)
    rejects { planner.demuxRows([missing]) }
    rejects { planner.demuxRows([sequencer[0] + [(field):' ']]) }
}
rejects { planner.demuxRows([]) }
rejects { planner.demuxRows([[run:'r',kit:'kit',barcode:'barcode01',sample:'s']]) }
rejects { planner.demuxRows([sequencer[0] + [alias:'bad sample name']]) }
rejects { planner.samples(pooled, planner.demuxRows([sequencer[0],sequencer[0]]), true) }
rejects { planner.samples(pooled, planner.demuxRows([sequencer[0],sequencer[1] + [alias:'BC3']]), true) }
rejects { planner.samples(pooled, planner.demuxRows([sequencer[0],sequencer[1] + [kit:'other-kit']]), true) }
rejects { planner.samples(rows, normalizedSheet, true) }
println 'Sequencer-sheet normalization and validation contracts passed'

def externalClair3 = 's3://example/models/r1041_e82_400bps_sup_v520_with_mv'
assert planner.reference(shared + [basecall_model:'sup', steps:[clair3:[model:externalClair3]]], [:], '/project').models.clair3 == externalClair3
rejects { planner.reference(shared + [basecall_model:'hac', steps:[clair3:[model:externalClair3]]], [:], '/project') }

assert planner.clair3Gpu([clair3_gpu:'auto', aws_gpu_queue:'gpu'], 'aws')
assert !planner.clair3Gpu([clair3_gpu:false, aws_gpu_queue:'gpu'], 'aws')
assert !planner.clair3Gpu([clair3_gpu:'auto', gpu_queue:'slurm-gpu'], 'aws')
assert planner.clair3Gpu([clair3_gpu:'auto', gpu_queue:'gpu'], 'slurm,apptainer')
assert planner.clair3Gpu([clair3_gpu:'auto', basecall_device:'0'], 'local,docker')
assert !planner.clair3Gpu([clair3_gpu:'auto'], 'local,docker')
planner.validateClair3Gpu([clair3_gpu:'auto', basecall_device:'0'], 'local,docker')
rejects { planner.validateClair3Gpu([clair3_gpu:true], 'aws') }
rejects { planner.validateClair3Gpu([clair3_gpu:'auto', gpu_queue:'gpu'], 'slurm') }
rejects { planner.validateClair3Gpu([clair3_gpu:'auto', basecall_device:'all'], 'local,docker') }

assert planner.clairstoGpu([clairsto_gpu:'auto', clair3_gpu:false, aws_gpu_queue:'gpu'], 'aws')
assert !planner.clairstoGpu([clairsto_gpu:false, clair3_gpu:true, aws_gpu_queue:'gpu'], 'aws')
planner.validateClairstoGpu([clairsto_gpu:'auto', clairsto_gpu_threads:1, aws_gpu_queue:'gpu'], 'aws')
rejects { planner.validateClairstoGpu([clairsto_gpu:true, clairsto_gpu_threads:1], 'aws') }
rejects { planner.validateClairstoGpu([clairsto_gpu:true, clairsto_gpu_threads:0, aws_gpu_queue:'gpu'], 'aws') }

assert planner.resolve([tertiary:true,callers:'deepsomatic'],hg38).callers == ['deepsomatic']
assert !planner.resolve([tertiary:true,callers:'clair3'],hg38).callers.contains('deepsomatic')
rejects { planner.resolve([tertiary:true,callers:'deepsomatic'],hs1) }
rejects { planner.resolve([secondary:true,callers:'deepsomatic'],hg38) }
assert planner.deepsomaticGpu([deepsomatic_gpu:'auto',aws_gpu_queue:'gpu'],'aws')
assert !planner.deepsomaticGpu([deepsomatic_gpu:false,aws_gpu_queue:'gpu'],'aws')
planner.validateDeepsomatic([deepsomatic_gpu:false,deepsomatic_cpus:8,deepsomatic_memory:'32 GB'],'local')
rejects { planner.validateDeepsomatic([deepsomatic_gpu:true,deepsomatic_cpus:8,deepsomatic_memory:'32 GB'],'aws') }
rejects { planner.validateDeepsomatic([deepsomatic_gpu:false,deepsomatic_cpus:0,deepsomatic_memory:'32 GB'],'local') }
assert statusClass.summarize(['s1'],['deepsomatic'], 'name\tstatus\nTERTIARY:CALLING:DEEPSOMATIC (s1)\tFAILED\n').find { it.analysis == 'deepsomatic' }.status == 'failed'

assert !planner.clairstoGpu([aws_gpu_queue:'gpu'], 'aws')

assert statusClass.summarize(['s1'],['sniffles'], 'name\tstatus\nTERTIARY:CALLING:FINALIZE_VARIANTS (s1:sniffles:sv)\tFAILED\n').find { it.analysis == 'sniffles' }.status == 'failed'

assert basecaller.directIdentity([bam:'a',sample_id:'s']) == 's'
assert basecaller.directIdentity([pod5:'a',experiment_id:'run1',demux_samplesheet:'sheet']) == 'run1'
assert basecaller.directIdentity([bam:'a',experiment_id:'run1',demux_samplesheet:'sheet']) == 'run1'
assert basecaller.directIdentity([input:'manifest']) == null
rejects { basecaller.directIdentity([bam:'a',sample_id:'oldrun',demux_samplesheet:'sheet']) }
rejects { basecaller.directIdentity([bam:'a',experiment_id:'run']) }
rejects { basecaller.directIdentity([bam:'a',demux_samplesheet:'sheet']) }
rejects { basecaller.directIdentity([input:'manifest',experiment_id:'run']) }
rejects { basecaller.directIdentity([bam:'a',experiment_id:'../bad',demux_samplesheet:'sheet']) }

def demultiplexer = loader.parseClass(new File('lib/Demultiplexing.groovy'))
def demuxMeta = [id:'r', kit:'kit', mappings:[[sample:'s',barcode:'barcode01']], require_moves:true]
def shardBams = [new File('shard1/kit_barcode01.bam'), new File('shard2/kit_barcode01.bam'),new File('shard2/unclassified.bam')]
assert demultiplexer.sampleBams(demuxMeta, shardBams)[0][1].size() == 2
assert demultiplexer.sampleBams(demuxMeta, shardBams)[0][0] == [id:'s',kit:'kit',input_run:'r',require_moves:true]
assert demultiplexer.sampleBams(demuxMeta, [shardBams[0]])[0][1].size() == 1
rejects { demultiplexer.sampleBams(demuxMeta, [shardBams[2]]) }
assert loader.parseClass(new File('lib/RunStatus.groovy')).summarize(['s'], [], 'name\tstatus\nPRIMARY:DEMULTIPLEX (r:batch_00000001)\tFAILED\n', [r:['s']]).find { it.analysis == 'alignment' }.status == 'failed'

assert !planner.adapterTrimming([noTrimAdapter:true,no_trim_adapter:false])
assert !planner.adapterTrimming(['no-trim-adapter':true,no_trim_adapter:false])

assert demultiplexer.sampleBams(demuxMeta, [shardBams[2]], false) == []
