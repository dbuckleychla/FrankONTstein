"""Shared offline presentation of small scientific aggregates; no BAM processing."""
import base64
import html
import math

CSS = '''body{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#203448;line-height:1.5;background:#fafbfd}h1,h2,h3{color:#164a63}h2{margin-top:2.5rem;border-bottom:2px solid #dde7ed;padding-bottom:.4rem}table{border-collapse:collapse;display:block;overflow-x:auto;margin:1rem 0;width:100%;font-size:.92rem}th,td{text-align:left;padding:.55rem .8rem;border-bottom:1px solid #dde7ed;vertical-align:top}th{background:#eaf1f5}tr:nth-child(even){background:#f2f6f8}a{color:#006a8e}figure{margin:1rem 0;padding:1rem;background:white;border:1px solid #dde7ed;border-radius:8px}figure img{width:100%}figcaption{font-size:.9rem;color:#526777}.cards{display:flex;gap:1rem;flex-wrap:wrap}.card{background:white;border:1px solid #dde7ed;border-radius:8px;padding:1rem;min-width:140px}.card strong{display:block;font-size:1.6rem;color:#164a63}.notice{padding:1rem;border-left:4px solid #af7b18;background:#fff6df}nav{display:flex;flex-wrap:wrap;gap:1rem;padding:1rem 0}summary{cursor:pointer}pre{white-space:pre-wrap}.histogram-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.histogram-grid figure{min-width:0;margin:0}.histogram-grid h3{font-size:1.1rem}@media(max-width:760px){.histogram-grid{grid-template-columns:1fr}}'''

def esc(value):
    return html.escape(str(value), quote=True)

def number(value, digits=0, percent=False):
    if value is None: return 'Unavailable'
    try: value=float(value)
    except (ValueError,TypeError): return str(value)
    if not math.isfinite(value): return 'Unavailable'
    if percent:
        if 0 < value < .001: return '<0.1%'
        return f'{value*100:,.1f}%'
    return f'{value:,.{digits}f}'

def label(value): return str(value).replace('_',' ').capitalize()

def display(value):
    if value is None: return 'Unavailable'
    if isinstance(value,bool): return 'Yes' if value else 'No'
    if isinstance(value,float): return number(value,2)
    if isinstance(value,int): return number(value)
    if isinstance(value,(list,tuple)): return '; '.join(display(v) for v in value) or 'None reported'
    if isinstance(value,dict): return '; '.join(f'{label(k)}: {display(v)}' for k,v in value.items()) or 'None reported'
    return str(value)

def table(headers, rows, empty='No reported records (analysis completed).'):
    rows=list(rows)
    if not rows: return '<p>'+esc(empty)+'</p>'
    return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(display(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'

def page(title, content):
    return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+esc(title)+'</title><style>'+CSS+'</style></head><body>'+content+'</body></html>'

def cards(items):
    return '<div class="cards">'+''.join('<div class="card">'+esc(k)+'<strong>'+esc(v)+'</strong></div>' for k,v in items)+'</div>'

def chart(title, series, xlabel, ylabel, logx=False, ymax=None, histogram=False, empty='Unavailable', bin_width=1):
    """Plot bounded aggregate series; coordinates already describe scientific metrics."""
    series=[(name,sorted(points)) for name,points in series if points]
    if not series: return '<p>'+esc(title)+': '+esc(empty)+'</p>'
    transform=lambda x: math.log10(max(1,x)) if logx else x
    xs=[transform(x) for _,ps in series for x,y in ps]; ys=[y for _,ps in series for x,y in ps]
    lo=min(0,min(xs)); hi=max(max(xs)+(1/12 if histogram and logx else bin_width if histogram else 0),lo+1); top=ymax or max(max(ys),1)
    xpixel=lambda x: 75+760*(transform(x)-lo)/(hi-lo)
    ypixel=lambda y: 280-230*y/top
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 390" role="img"><title>'+esc(title)+'</title><rect width="900" height="390" fill="white"/>']
    for i in range(6):
        y=top*i/5; py=ypixel(y)
        s.append(f'<path d="M75 {py}H835" stroke="#dce5eb"/><text x="65" y="{py+4}" text-anchor="end" font-size="12">{y:,.1f}</text>')
    ticks=range(math.ceil(lo),math.floor(hi)+1) if logx else [lo+(hi-lo)*i/5 for i in range(6)]
    for tick in ticks:
        value=10**tick if logx else tick; px=xpixel(value)
        tick_label=format(value, ',.2f' if hi<=1 else ',.0f')
        s.append(f'<text x="{px}" y="305" text-anchor="middle" font-size="12">{tick_label}</text>')
    colors=['#007b91','#d47827','#7358aa','#438343']
    for i,(name,points) in enumerate(series):
        color=colors[i%len(colors)]; coords=' '.join(f'{xpixel(x):.2f},{ypixel(y):.2f}' for x,y in points)
        if histogram:
            for x,y in points:
                end=x*10**(1/12) if logx else x+bin_width
                width=max(.3,min(40,xpixel(end)-xpixel(x)))
                s.append(f'<rect x="{xpixel(x):.2f}" y="{ypixel(y):.2f}" width="{width:.2f}" height="{280-ypixel(y):.2f}" fill="{color}" fill-opacity=".45"><title>{esc(name)}: {x:,.0f}–{end:,.0f}; {y:.2f}</title></rect>')
        else:
            s.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        s.append(f'<text x="{80+(i%2)*390}" y="{350+(i//2)*20}" fill="{color}" font-size="13">{esc(name)}</text>')
    s.extend([f'<text x="450" y="330" text-anchor="middle">{esc(xlabel)}</text>',f'<text x="16" y="170" transform="rotate(-90 16 170)" text-anchor="middle">{esc(ylabel)}</text>','</svg>'])
    encoded=base64.b64encode(''.join(s).encode()).decode()
    return f'<figure><h3>{esc(title)}</h3><img alt="{esc(title)}" src="data:image/svg+xml;base64,{encoded}"><figcaption>{esc(xlabel)} · {esc(ylabel)}</figcaption></figure>'

def hist_points(hist, percent=False, log=False):
    bins={}
    for key,count in hist.items():
        x=float(key)
        # Compact long tails to 12 logarithmic bins per decade.
        bucket=10**(math.floor(math.log10(max(1,x))*12)/12) if log else x
        bins[bucket]=bins.get(bucket,0)+count
    total=sum(bins.values())
    return [(x,n*100/total if percent and total else n) for x,n in sorted(bins.items())]

def depth_bars(coverage):
    scopes=['genome','targets','enrichment','off_enrichment']
    values=[coverage.get(q,{}).get(k,{}).get('mean') for k in scopes for q in ['0','20']]
    top=max([v for v in values if v is not None]+[1])
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 330"><title>Mean coverage by region</title><rect width="900" height="330" fill="white"/>']
    for i,k in enumerate(scopes):
        for j,q in enumerate(['0','20']):
            value=coverage.get(q,{}).get(k,{}).get('mean')
            if value is None: continue
            height=value/top*220;x=80+i*205+j*65
            svg.append(f'<rect x="{x}" y="{250-height}" width="55" height="{height}" fill="{["#007b91","#d47827"][j]}"/><text x="{x}" y="{240-height}" font-size="13">{value:.1f}×</text>')
        svg.append(f'<text x="{70+i*205}" y="275" font-size="14">{esc(label(k))}</text>')
    svg.append('<text x="70" y="315" fill="#007b91">MAPQ ≥0</text><text x="220" y="315" fill="#d47827">MAPQ ≥20</text></svg>')
    encoded=base64.b64encode(''.join(svg).encode()).decode()
    return '<figure><h3>Mean coverage by region</h3><img alt="Mean coverage by region, MAPQ 0 and 20" src="data:image/svg+xml;base64,'+encoded+'"><figcaption>Mean depth (×); common linear scale. See table for exact denominators.</figcaption></figure>'


def metric_rows(data, prefix=''):
    for key,value in data.items():
        name=(prefix+' / ' if prefix else '')+label(key)
        if isinstance(value,dict): yield from metric_rows(value,name)
        else:
            if 'fraction' in key or key in ('alignment_rate','mean_beta','weighted_beta'):
                value=number(value,percent=True)
            elif isinstance(value,(int,float)) and not isinstance(value,bool):
                value=number(value,1 if 'depth' in key or 'coverage' in key else 0)
            yield [name,value]


def qc_content(data):
    a=data.get('alignment',{}); lengths=a.get('read_lengths',{}); coverage=a.get('coverage',{})
    out=[cards([('Primary reads',number(a.get('counts',{}).get('primary_reads'))),('Aligned reads',number(a.get('alignment_rate'),percent=True)),('On-enrichment reads',number(a.get('on_enrichment_fraction_mapped'),percent=True))])]
    out.append('<h3>Read lengths</h3><p>Sequenced query lengths of primary reads, including duplicate/QC-failed flags. Any aligned-block overlap assigns a mapped read to a region. Target and enrichment comparisons overlap and cannot be summed. Unmapped reads are separate.</p>')
    groups=['all','mapped','unmapped','on_target','off_target','on_enrichment','off_enrichment']
    out.append(table(['Scope','Reads','Bases','Mean (bp)','Median (bp)','N50 (bp)'],[[label(k)]+[number(lengths.get(k,{}).get(f)) for f in ['reads','bases','mean','median','n50']] for k in groups]))
    out.append('<div class="histogram-grid">')
    for title,keys in [('Target read lengths',['on_target','off_target']),('Enrichment read lengths',['on_enrichment','off_enrichment'])]:
        out.append(chart(title,[(label(k),hist_points(lengths.get(k,{}).get('histogram',{}),True,True)) for k in keys],'Read length (bp, log scale; 12 bins/decade)','Reads in group (%)',True,histogram=True,empty='No reads observed' if all(k in lengths for k in keys) else 'Unavailable'))
    out.append('</div>')
    out.append('<h3>Yield fractions</h3>')
    totals=lengths.get('all',{})
    out.append(table(['Scope','Fraction of all reads','Fraction of all sequenced bases'],[[label(k)]+[number(lengths[k].get(f,0)/totals[f] if totals.get(f) else None,percent=True) for f in ['reads','bases']] for k in groups[1:] if k in lengths]))
    out.append(chart('Mapping quality', [('Mapped primary reads',hist_points(a.get('mapq',{}),True))],'MAPQ','Mapped reads (%)',histogram=True))
    out.append('<h3>Coverage</h3><p>Primary chromosomes 1–22/X/Y; denominators are region bases including zero-depth positions. Deletions, reference skips, secondary and supplementary alignments are excluded. MAPQ 0 and 20 are shown separately.</p>')
    scopes=['genome','targets','enrichment','off_enrichment']
    out.append(table(['MAPQ ≥','Region','Region bases','Mean depth (×)','≥1×','≥5×','≥10×','≥20×'],[[q,label(k),number(d.get('bases')),number(d.get('mean'),1)]+[number(d.get('breadth',{}).get(str(t)),percent=True) for t in [1,5,10,20]] for q in ['0','20'] for k in scopes if (d:=coverage.get(q,{}).get(k))]))
    out.append(depth_bars(coverage))
    out.append('<h3>CpG methylation</h3>')
    for scope,mods in data.get('methylation',{}).items():
        if not isinstance(mods,dict): continue
        out.append('<h4>'+esc(label(scope))+'</h4>')
        out.append(table(['Modification','Availability','Callable sites','Reference CpGs','Sites at depth ≥10','Mean beta','Weighted beta'],[[mod,'Available' if d.get('available') else 'Unavailable',number(d.get('sites') if d.get('available') else None),number(d.get('reference_cpgs')),number(d.get('sites_at_depth',{}).get('10') if d.get('available') else None),number(d.get('mean_beta'),percent=True),number(d.get('weighted_beta'),percent=True)] for mod in ['5mC','5hmC'] for d in [mods.get(mod,{})]]))
    methyl=data.get('methylation',{}).get('genome',{}).get('5mC',{})
    points=hist_points(methyl.get('beta_hist',{}),True) if methyl.get('available') else []
    out.append(chart('5mCpG beta distribution', [('5mCpG',[(x/100,y) for x,y in points])],
                     'Beta (0–1; primary chromosomes)','CpG sites (%)',histogram=True,
                     empty='No observations' if methyl.get('available') else 'Unavailable', bin_width=.01))
    return ''.join(out)
