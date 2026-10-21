"""Painel visual (HTML autonomo) do ciclo completo: dados -> score -> dossie.
O score e uma HEURISTICA DE PRIORIZACAO transparente (nao e previsao de venda).
Cada componente e mostrado por empresa, para ser contestado e ajustado.
"""
import json
from datetime import date
from pathlib import Path
from mintel.db import connect
from mintel.dossier import build_company_dossier

WEIGHTS = {"size_fit": 40, "headcount_fit": 20, "labor_intensity": 20, "data_completeness": 20}
SEGMENT_LABEL = {"logistics": "Logistica", "wholesale_industrial_parts": "Atacado industrial", "other": "Outro"}


def _band(x, zero_lo, full_lo, full_hi, zero_hi):
    """1.0 dentro da faixa ideal, cai linearmente ate 0 nas bordas."""
    if x is None:
        return 0.0
    if full_lo <= x <= full_hi:
        return 1.0
    if x < full_lo:
        return max(0.0, (x - zero_lo) / (full_lo - zero_lo))
    return max(0.0, (zero_hi - x) / (zero_hi - full_hi))


def score_company(d):
    m = (d.get("financials") or {}).get("metrics", {})
    rev = m.get("revenue", {}).get("amount")
    emp = m.get("employees", {}).get("amount")
    ratio = ((d.get("financials") or {}).get("derived") or {}).get("personnel_cost_ratio_pct")
    present = sum([
        any(i["type"] == "partita_iva" for i in d["identifiers"]),
        any(i["type"] == "codice_fiscale" for i in d["identifiers"]),
        any(i["type"] == "rea" for i in d["identifiers"]),
        rev is not None, emp is not None, ratio is not None])
    parts = {
        "size_fit": WEIGHTS["size_fit"] * _band(rev, 500_000, 4_000_000, 7_000_000, 12_000_000),
        "headcount_fit": WEIGHTS["headcount_fit"] * _band(emp, 3, 20, 45, 80),
        "labor_intensity": WEIGHTS["labor_intensity"] * _band(ratio, 5, 12, 15, 25),
        "data_completeness": WEIGHTS["data_completeness"] * present / 6,
    }
    total = round(sum(parts.values()), 1)
    tier = "A" if total >= 80 else "B" if total >= 55 else "C"
    return total, tier, {k: round(v, 1) for k, v in parts.items()}


def collect(db_path=None):
    conn = connect(db_path) if db_path else connect()
    ids = [r[0] for r in conn.execute("SELECT company_id FROM companies ORDER BY company_id")]
    conn.close()
    out = []
    for cid in ids:
        d = build_company_dossier(cid, db_path=db_path)
        score, tier, parts = score_company(d)
        fin = d.get("financials") or {}
        m = fin.get("metrics", {})
        out.append({
            "id": cid, "name": d["legal_name"], "form": d["legal_form"], "segment": d["segment"],
            "segment_label": SEGMENT_LABEL.get(d["segment"], d["segment"]),
            "comune": d["comune"], "province": d["province"], "address": d["address"],
            "ateco": d["ateco_code"], "ateco_version": d["ateco_version"], "status": d["status"],
            "identifiers": d["identifiers"], "fiscal_year": fin.get("fiscal_year"), "source": fin.get("source"),
            "revenue": m.get("revenue", {}).get("amount"), "employees": m.get("employees", {}).get("amount"),
            "personnel_cost": m.get("personnel_cost", {}).get("amount"),
            "rev_per_emp": (fin.get("derived") or {}).get("revenue_per_employee"),
            "labor_ratio": (fin.get("derived") or {}).get("personnel_cost_ratio_pct"),
            "flags": d["data_quality_flags"], "playbook_title": d["playbook"]["title"],
            "hypotheses": d["playbook"]["hypotheses"],
            "score": score, "tier": tier, "score_parts": parts})
    return out


def build_report(db_path=None, out_path="reports/dashboard.html", synthetic=True):
    data = {"companies": collect(db_path), "weights": WEIGHTS, "generated": date.today().isoformat(), "synthetic": synthetic}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = HTML.replace("/*DATA*/null", payload)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)


HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Piemonte Market Intel - Painel</title>
<style>
:root{--bg:#f4f6fa;--card:#fff;--ink:#16202e;--mut:#6b778a;--line:#e3e8ef;--navy:#12263f;--log:#1f77b4;--ws:#e08a1e;--oth:#7a8699;--A:#1b9a5b;--B:#d9a00f;--C:#a9b2c0}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--navy);color:#fff;padding:22px 32px}header h1{margin:0;font-size:20px}header p{margin:4px 0 0;color:#b9c6d8;font-size:13px}
.banner{background:#fff4d6;border-bottom:1px solid #f0d98a;color:#6a5200;padding:8px 32px;font-size:13px}
main{padding:24px 32px;max-width:1400px;margin:0 auto}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.kpi .v{font-size:26px;font-weight:700}.kpi .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.grid{display:grid;grid-template-columns:1.1fr 1fr;gap:14px;margin-bottom:18px}
h2{font-size:14px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.bar{display:flex;align-items:center;gap:8px;margin:5px 0;cursor:pointer}.bar .n{width:190px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .t{flex:1;background:#eef1f6;border-radius:4px;height:16px}.bar .f{height:16px;border-radius:4px}.bar .s{width:38px;text-align:right;font-weight:600;font-size:12px}
.legend{display:flex;gap:14px;font-size:12px;color:var(--mut);margin-top:6px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}
.seg{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.seg .card{padding:12px}.seg b{font-size:18px}
.tools{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}input,select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}th{background:#f8fafc;cursor:pointer;color:var(--mut);font-size:12px;text-transform:uppercase;user-select:none}
tr.r:hover{background:#f0f5ff;cursor:pointer}.num{text-align:right}
.tier{display:inline-block;min-width:24px;text-align:center;border-radius:5px;color:#fff;font-weight:700;padding:1px 6px}.tA{background:var(--A)}.tB{background:var(--B)}.tC{background:var(--C)}
.pill{padding:2px 8px;border-radius:10px;font-size:11px;color:#fff}
#drawer{position:fixed;top:0;right:-640px;width:620px;max-width:100%;height:100%;background:#fff;box-shadow:-8px 0 30px rgba(0,0,0,.18);transition:right .25s;overflow:auto;padding:24px;z-index:9}
#drawer.open{right:0}#drawer h3{margin:0 0 4px;font-size:18px}.x{float:right;cursor:pointer;font-size:22px;color:var(--mut)}
.sec{margin-top:18px}.sec h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);border-bottom:1px solid var(--line);padding-bottom:4px}
.kv{display:grid;grid-template-columns:170px 1fr;gap:3px 10px;font-size:13px}.kv span:nth-child(odd){color:var(--mut)}
.hyp{background:#f3f7ff;border-left:3px solid #4a7bd0;padding:8px 10px;margin:8px 0;border-radius:4px;font-size:13px}.hyp i{color:#34507d}
.flag{background:#fff4d6;border-left:3px solid #e0a800;padding:6px 10px;margin:4px 0;font-size:13px}
.pb{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px}.pb .t{flex:1;background:#eef1f6;height:10px;border-radius:5px}.pb .f{height:10px;border-radius:5px;background:var(--navy)}
footer{padding:20px 32px;color:var(--mut);font-size:12px;text-align:center}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
</style></head><body>
<header><h1>Piemonte Market Intel &mdash; Painel de Contas</h1><p id="sub"></p></header>
<div class="banner" id="ban"></div>
<main>
<div class="kpis" id="kpis"></div>
<div class="grid"><div class="card"><h2>Top 15 por score de prioridade (clique para abrir o dossie)</h2><div id="top"></div></div>
<div class="card"><h2>Receita x funcionarios (cada ponto = 1 empresa)</h2><div id="sc"></div><div class="legend" id="lg"></div></div></div>
<div class="grid"><div class="card"><h2>Resumo por segmento</h2><div class="seg" id="seg"></div></div>
<div class="card"><h2>Como o score e calculado</h2><div style="font-size:13px;color:#3b475a" id="how"></div></div></div>
<div class="tools"><input id="q" placeholder="Buscar empresa, comune ou P.IVA..."><select id="fs"><option value="">Todos os segmentos</option></select><select id="fc"><option value="">Todos os comunes</option></select><select id="ft"><option value="">Todos os tiers</option><option>A</option><option>B</option><option>C</option></select><span id="cnt" style="align-self:center;color:#6b778a"></span></div>
<table><thead><tr id="th"></tr></thead><tbody id="tb"></tbody></table>
</main>
<div id="drawer"></div>
<footer id="ft2"></footer>
<script>
const D=/*DATA*/null;const C=D.companies;
const COL={logistics:'#1f77b4',wholesale_industrial_parts:'#e08a1e',other:'#7a8699'};
const eur=n=>n==null?'—':'€ '+Math.round(n).toLocaleString('pt-BR');
const $=id=>document.getElementById(id);
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
$('sub').textContent='Ciclo completo: dados -> validacao -> score -> dossie | gerado em '+D.generated;
$('ban').innerHTML=D.synthetic?'<b>DADOS SINTETICOS DE TESTE.</b> Nomes, P.IVA e numeros sao ficticios; serve para visualizar como o produto final ficara com a lista real.':'Dados reais.';
const A=C.filter(c=>c.tier==='A').length;
$('kpis').innerHTML=[['Empresas',C.length],['Tier A',A],['Receita media',eur(avg(C.map(c=>c.revenue).filter(x=>x!=null)))],['Funcionarios (media)',avg(C.map(c=>c.employees).filter(x=>x!=null)).toFixed(0)],['Score medio',avg(C.map(c=>c.score)).toFixed(1)]].map(k=>'<div class="card kpi"><div class="v">'+k[1]+'</div><div class="l">'+k[0]+'</div></div>').join('');
const sorted=[...C].sort((a,b)=>b.score-a.score);
$('top').innerHTML=sorted.slice(0,15).map(c=>'<div class="bar" onclick="openD('+c.id+')"><div class="n" title="'+c.name+'">'+c.name+'</div><div class="t"><div class="f" style="width:'+c.score+'%;background:'+COL[c.segment]+'"></div></div><div class="s">'+c.score+'</div></div>').join('');
(function(){const W=520,H=300,p=44;const xs=C.map(c=>c.employees||0),ys=C.map(c=>c.revenue||0);const xm=Math.max(...xs)*1.08,ym=Math.max(...ys)*1.08;
let s='<svg viewBox="0 0 '+W+' '+H+'" width="100%">';
for(let i=0;i<=4;i++){const y=H-p-(H-2*p)*i/4;s+='<line x1="'+p+'" x2="'+(W-10)+'" y1="'+y+'" y2="'+y+'" stroke="#e3e8ef"/><text x="'+(p-6)+'" y="'+(y+4)+'" font-size="10" text-anchor="end" fill="#6b778a">'+(ym*i/4/1e6).toFixed(0)+'M</text>';}
for(let i=0;i<=4;i++){const x=p+(W-p-10)*i/4;s+='<text x="'+x+'" y="'+(H-p+16)+'" font-size="10" text-anchor="middle" fill="#6b778a">'+Math.round(xm*i/4)+'</text>';}
s+='<text x="'+(W/2)+'" y="'+(H-6)+'" font-size="11" text-anchor="middle" fill="#6b778a">funcionarios</text>';
C.forEach(c=>{const x=p+(W-p-10)*(c.employees||0)/xm,y=H-p-(H-2*p)*(c.revenue||0)/ym;s+='<circle cx="'+x+'" cy="'+y+'" r="'+(4+c.score/20)+'" fill="'+COL[c.segment]+'" fill-opacity=".72" stroke="#fff" style="cursor:pointer" onclick="openD('+c.id+')"><title>'+c.name+' | score '+c.score+'</title></circle>';});
$('sc').innerHTML=s+'</svg>';
const segs=[...new Set(C.map(c=>c.segment))];
$('lg').innerHTML=segs.map(g=>'<span><span class="dot" style="background:'+COL[g]+'"></span>'+C.find(c=>c.segment===g).segment_label+'</span>').join('')+'<span>(tamanho do ponto = score)</span>';})();
$('seg').innerHTML=[...new Set(C.map(c=>c.segment))].map(g=>{const a=C.filter(c=>c.segment===g);return '<div class="card"><span class="dot" style="background:'+COL[g]+'"></span>'+a[0].segment_label+'<br><b>'+a.length+'</b> empresas<br><span style="color:#6b778a">receita media '+eur(avg(a.map(c=>c.revenue||0)))+'<br>score medio '+avg(a.map(c=>c.score)).toFixed(1)+' | tier A: '+a.filter(c=>c.tier==='A').length+'</span></div>';}).join('');
$('how').innerHTML='<p>Heuristica de priorizacao (0-100), <b>nao e previsao de venda</b>. Soma de 4 componentes, todos visiveis no dossie:</p><ul style="padding-left:18px"><li><b>Porte (40)</b>: receita ideal entre € 4M e € 7M</li><li><b>Equipe (20)</b>: 20 a 45 funcionarios</li><li><b>Intensidade de mao de obra (20)</b>: folha entre 12% e 15% da receita</li><li><b>Completude dos dados (20)</b>: P.IVA, CF, REA, receita, equipe, folha</li></ul><p>Tier A &ge; 80, B &ge; 55, C abaixo. Pesos e faixas sao ajustaveis em <code>report.py</code> e devem ser calibrados com os resultados das conversas reais.</p>';
const cols=[['id','#'],['name','Empresa'],['segment_label','Segmento'],['comune','Comune'],['revenue','Receita'],['employees','Func.'],['labor_ratio','Folha %'],['score','Score'],['tier','Tier']];
let sk='score',sd=-1;
$('th').innerHTML=cols.map(c=>'<th data-k="'+c[0]+'">'+c[1]+'</th>').join('');
document.querySelectorAll('th').forEach(h=>h.onclick=()=>{const k=h.dataset.k;sd=sk===k?-sd:(k==='name'||k==='comune'||k==='segment_label'?1:-1);sk=k;draw();});
[...new Set(C.map(c=>c.segment))].forEach(g=>$('fs').insertAdjacentHTML('beforeend','<option value="'+g+'">'+C.find(c=>c.segment===g).segment_label+'</option>'));
[...new Set(C.map(c=>c.comune))].sort().forEach(g=>$('fc').insertAdjacentHTML('beforeend','<option>'+g+'</option>'));
['q','fs','fc','ft'].forEach(i=>$(i).oninput=draw);
function draw(){const q=$('q').value.toLowerCase();let a=C.filter(c=>(!$('fs').value||c.segment===$('fs').value)&&(!$('fc').value||c.comune===$('fc').value)&&(!$('ft').value||c.tier===$('ft').value)&&(!q||(c.name+' '+c.comune+' '+c.identifiers.map(i=>i.value).join(' ')).toLowerCase().includes(q)));
a.sort((x,y)=>{const u=x[sk],v=y[sk];return (typeof u==='string'?u.localeCompare(v):(u||0)-(v||0))*sd;});
$('cnt').textContent=a.length+' de '+C.length;
$('tb').innerHTML=a.map(c=>'<tr class="r" onclick="openD('+c.id+')"><td>'+c.id+'</td><td>'+c.name+'</td><td><span class="pill" style="background:'+COL[c.segment]+'">'+c.segment_label+'</span></td><td>'+c.comune+'</td><td class="num">'+eur(c.revenue)+'</td><td class="num">'+(c.employees||'—')+'</td><td class="num">'+(c.labor_ratio==null?'—':c.labor_ratio+'%')+'</td><td class="num"><b>'+c.score+'</b></td><td><span class="tier t'+c.tier+'">'+c.tier+'</span></td></tr>').join('');}
function openD(id){const c=C.find(x=>x.id===id);const names={size_fit:'Porte',headcount_fit:'Equipe',labor_intensity:'Mao de obra',data_completeness:'Completude'};
$('drawer').innerHTML='<span class="x" onclick="closeD()">&times;</span><h3>'+c.name+'</h3><div style="color:#6b778a">#'+c.id+' | '+c.playbook_title+' | status: '+c.status+'</div>'+
'<div class="sec"><h4>Score de prioridade: '+c.score+' <span class="tier t'+c.tier+'">'+c.tier+'</span></h4>'+Object.keys(c.score_parts).map(k=>'<div class="pb"><span style="width:110px">'+names[k]+'</span><div class="t"><div class="f" style="width:'+(c.score_parts[k]/D.weights[k]*100)+'%"></div></div><span>'+c.score_parts[k]+'/'+D.weights[k]+'</span></div>').join('')+'</div>'+
'<div class="sec"><h4>1. Fatos cadastrais (com fonte)</h4><div class="kv"><span>Forma</span><span>'+(c.form||'—')+'</span><span>Endereco</span><span>'+(c.address||'—')+', '+c.comune+' ('+c.province+')</span><span>ATECO</span><span>'+(c.ateco||'—')+' (versao '+(c.ateco_version||'?')+')</span>'+c.identifiers.map(i=>'<span>'+i.type+'</span><span>'+i.value+' <small style="color:#6b778a">('+i.source+')</small></span>').join('')+'</div></div>'+
'<div class="sec"><h4>2. Fatos financeiros &mdash; exercicio '+(c.fiscal_year||'?')+'</h4><div class="kv"><span>Receita</span><span>'+eur(c.revenue)+'</span><span>Funcionarios</span><span>'+(c.employees||'—')+'</span><span>Custo de pessoal</span><span>'+eur(c.personnel_cost)+'</span><span>Receita / funcionario</span><span>'+eur(c.rev_per_emp)+'</span><span>Folha / receita</span><span>'+(c.labor_ratio==null?'—':c.labor_ratio+'%')+'</span><span>Fonte</span><span>'+(c.source||'—')+'</span></div></div>'+
'<div class="sec"><h4>3. Limites de confiabilidade</h4>'+(c.flags.length?c.flags.map(f=>'<div class="flag">'+f+'</div>').join(''):'Sem alertas')+'</div>'+
'<div class="sec"><h4>4. Hipoteses a validar (nao sao fatos)</h4>'+c.hypotheses.map(h=>'<div class="hyp"><b>'+h.topic+'</b><br>'+h.hypothesis+'<br><i>Pergunta de descoberta: &ldquo;'+h.validation_question+'&rdquo;</i></div>').join('')+'</div>';
$('drawer').classList.add('open');}
function closeD(){$('drawer').classList.remove('open');}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeD();});
$('ft2').textContent='Piemonte Market Intel | fatos separados de hipoteses | score e heuristica de priorizacao, nao previsao';
draw();
</script></body></html>"""
