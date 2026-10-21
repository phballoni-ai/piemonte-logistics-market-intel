"""
Modulo de Inteligencia de Contas (Dossier e Hipoteses de Abordagem).
Gera fichas estruturadas separando estritamente:
- Fatos cadastrais e economicos com fonte
- Data quality flags (lacunas e limites dos dados)
- Hipoteses de dor e oportunidade (claramente rotuladas como hipoteses)
- Perguntas de validacao para conversa de campo (discovery)
- Historico de interacoes de campo (reunioes, desfecho, anotacoes)
- Observacoes qualitativas adicionais
"""
from pathlib import Path
from mintel.db import connect
from mintel.interactions import get_company_interactions, get_company_observations

SEGMENT_PLAYBOOKS = {
    "logistics": {
        "title": "Transporte Rodoviario & Logistica de Distribuicao",
        "hypotheses": [
            {
                "topic": "Eficiencia de Frotas & Margem Operacional",
                "hypothesis": "Margem operacional sob pressao por custos de combustivel e folha; oportunidade em roteirizacao dinamica, telemetria e reducao de viagens vazias (backhaul).",
                "validation_question": "Como voces monitoram hoje o impacto da flutuacao do diesel e a eficiencia de retorno das cargas na malha regional?"
            },
            {
                "topic": "SLA & Visibilidade para Embarcadores B2B",
                "hypothesis": "Clientes industriais do polo de Torino/Pinerolo demandam previsibilidade Just-in-Time; falta de portal integrado ou rastreamento em tempo real gera atrito operacional.",
                "validation_question": "Qual e a principal exigencia que seus maiores clientes industriais fazem em termos de rastreamento de entregas e comprovacao digital (e-POD)?"
            }
        ]
    },
    "wholesale_industrial_parts": {
        "title": "Comercio Atacadista de Maquinas, Pecas e Componentes",
        "hypotheses": [
            {
                "topic": "Capital de Giro & Giro de Estoque",
                "hypothesis": "Risco de estoque obsoleto ou imobilizado em pecas de medio/baixo giro, convivendo com eventuais rupturas em componentes criticos da Curva A.",
                "validation_question": "Como voces equilibram hoje a necessidade de entrega imediata para oficinas/fabricas locais sem sobrecarregar o capital de giro em estoque parado?"
            },
            {
                "topic": "Digitalizacao do Atendimento & Cotacoes B2B",
                "hypothesis": "Tempo excessivo da equipe comercial respondendo cotacoes repetitivas por telefone/WhatsApp/e-mail em vez de focar na expansao de contas estrategicas.",
                "validation_question": "Quanto do tempo do time comercial interno e gasto montando orcamentos manuais de pecas versus desenvolvimento ativo de clientes?"
            }
        ]
    },
    "other": {
        "title": "Segmento Geral B2B",
        "hypotheses": [
            {
                "topic": "Eficiencia de Processos & Margem",
                "hypothesis": "Processos operacionais dependentes de rotinas manuais com oportunidade de automacao e visibilidade financeira.",
                "validation_question": "Qual o principal gargalo operacional que consome tempo da diretoria no dia a dia da operacao?"
            }
        ]
    }
}


def build_company_dossier(company_id: int, db_path=None) -> dict:
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()

    cur.execute(
        """SELECT company_id, legal_name, legal_form, comune, province, address,
                  ateco_code, ateco_version, segment, status, created_at
           FROM companies WHERE company_id = ?""",
        (company_id,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Empresa ID {company_id} nao encontrada no banco.")

    cols = [d[0] for d in cur.description]
    company = dict(zip(cols, row))

    cur.execute(
        """SELECT i.id_type, i.value, s.name as source_name, s.source_type
           FROM company_identifiers i
           LEFT JOIN data_sources s ON i.source_id = s.source_id
           WHERE i.company_id = ?""",
        (company_id,)
    )
    company["identifiers"] = [
        {"type": r[0], "value": r[1], "source": r[2], "source_type": r[3]}
        for r in cur.fetchall()
    ]

    cur.execute(
        """SELECT s.statement_id, s.fiscal_year, s.statement_type, ds.name as source_name
           FROM financial_statements s
           LEFT JOIN data_sources ds ON s.source_id = ds.source_id
           WHERE s.company_id = ?
           ORDER BY s.fiscal_year DESC, s.version DESC LIMIT 1""",
        (company_id,)
    )
    stmt_row = cur.fetchone()
    financials = None
    if stmt_row:
        stmt_id, f_year, s_type, s_source = stmt_row
        cur.execute(
            """SELECT item, amount, definition FROM financial_values WHERE statement_id = ?""",
            (stmt_id,)
        )
        vals = {r[0]: {"amount": r[1], "definition": r[2]} for r in cur.fetchall()}
        financials = {
            "fiscal_year": f_year,
            "statement_type": s_type,
            "source": s_source,
            "metrics": vals
        }
        rev = vals.get("revenue", {}).get("amount")
        emp = vals.get("employees", {}).get("amount")
        pc = vals.get("personnel_cost", {}).get("amount")
        derived = {}
        if rev and emp and emp > 0:
            derived["revenue_per_employee"] = round(rev / emp, 2)
        if rev and pc:
            derived["personnel_cost_ratio_pct"] = round((pc / rev) * 100, 2)
        financials["derived"] = derived
    company["financials"] = financials

    flags = []
    if not any(i["type"] == "partita_iva" for i in company["identifiers"]):
        flags.append("P.IVA ausente no cadastro")
    if not company.get("financials"):
        flags.append("Nenhum balanco/dado financeiro registrado ainda")
    if company.get("status") == "unverified":
        flags.append("Cadastro preliminar (ainda nao verificado no Registro Imprese oficial)")
    company["data_quality_flags"] = flags

    seg = company.get("segment") or "other"
    playbook = SEGMENT_PLAYBOOKS.get(seg, SEGMENT_PLAYBOOKS["other"])
    company["playbook"] = playbook

    conn.close()

    company["interactions"] = get_company_interactions(company_id, db_path=db_path)
    company["observations"] = get_company_observations(company_id, db_path=db_path)

    if company["interactions"]:
        company["last_interaction"] = company["interactions"][0]
        company["funnel_status"] = company["interactions"][0]["outcome"]
    else:
        company["last_interaction"] = None
        company["funnel_status"] = "no_contact"

    return company


def format_dossier_markdown(dossier: dict) -> str:
    c = dossier
    p_title = c["playbook"]["title"]
    lines = [
        f"# Dossier Executivo: {c['legal_name']}",
        f"*ID Interno:* #{c['company_id']} | *Segmento:* {p_title} | *Status de Prospeccao:* `{c.get('funnel_status', 'no_contact')}`",
        "",
        "## 1. Identidade Cadastral & Localizacao",
        f"- **Razao Social:** {c['legal_name']} ({c['legal_form'] or 'N/A'})",
        f"- **Localizacao:** {c['address'] or 'Sede'}, {c['comune']} ({c['province']})",
        f"- **Codigo ATECO:** `{c['ateco_code'] or 'N/D'}` (Versao: {c['ateco_version'] or 'N/D'})"
    ]
    for ident in c["identifiers"]:
        lines.append(f"- **{ident['type'].upper()}:** `{ident['value']}` (Fonte: *{ident['source']}*)")

    lines.append("")
    lines.append("## 2. Fatos Financeiros & Dimensionamento")
    fin = c.get("financials")
    if fin:
        lines.append(f"*Ano Fiscal de Referencia:* **{fin['fiscal_year']}** (Fonte: {fin['source']})")
        m = fin["metrics"]
        if "revenue" in m:
            lines.append(f"- **Faturamento (Valor da Producao):** EUR {m['revenue']['amount']:,.2f}")
        if "employees" in m:
            lines.append(f"- **Quadro de Funcionarios:** {int(m['employees']['amount'])} colaboradores")
        if "personnel_cost" in m:
            lines.append(f"- **Custo de Pessoal:** EUR {m['personnel_cost']['amount']:,.2f}")

        d = fin.get("derived", {})
        if "revenue_per_employee" in d:
            lines.append(f"- **Produtividade (Receita / Funcionario):** EUR {d['revenue_per_employee']:,.2f}/colab")
        if "personnel_cost_ratio_pct" in d:
            lines.append(f"- **Peso da Folha / Faturamento:** {d['personnel_cost_ratio_pct']}%")
    else:
        lines.append("*Aviso:* Nenhum balanco publico vinculado a esta conta.")

    lines.append("")
    lines.append("## 3. Limites de Confiabilidade (Data Quality Flags)")
    if c["data_quality_flags"]:
        for flag in c["data_quality_flags"]:
            lines.append(f"- ⚠️ **Flag:** {flag}")
    else:
        lines.append("- ✅ Dados cadastrais e financeiros integros.")

    lines.append("")
    lines.append("## 4. Hipoteses de Abordagem & Perguntas de Validacao")
    lines.append("> **Importante:** Estas teses sao *hipoteses a validar* com base no setor e porte, NAO certezas previas.\n")
    for idx, h in enumerate(c["playbook"]["hypotheses"], start=1):
        lines.append(f"### Hipotese {idx}: {h['topic']}")
        lines.append(f"**Tese Operacional:** {h['hypothesis']}")
        q = h["validation_question"]
        lines.append(f"**Pergunta de Descoberta (Campo):** \"{q}\"\n")

    if c.get("interactions"):
        lines.append("## 5. Historico de Contatos & Conversas de Campo")
        for it in c["interactions"]:
            lines.append(f"- **{it['occurred_on']}** | Desfecho: `{it['outcome']}` | Cargo: {it['role_of_contact'] or 'N/A'}")
            if it.get("stated_pain"):
                lines.append(f"  - *Dor citada:* {it['stated_pain']}")
            if it.get("next_step"):
                lines.append(f"  - *Proximo passo:* {it['next_step']}")
        lines.append("")

    if c.get("observations"):
        lines.append("## 6. Observacoes Qualitativas Avulsas")
        for ob in c["observations"]:
            lines.append(f"- **{ob['field']}:** {ob['value']} *(Data: {ob['date']} | Fonte: {ob['source']})*")
        lines.append("")

    return "\n".join(lines)


def export_all_dossiers_markdown(db_path=None, output_dir=None) -> list:
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    cur.execute("SELECT company_id, legal_name FROM companies ORDER BY company_id ASC")
    rows = cur.fetchall()
    conn.close()

    out_path = Path(output_dir) if output_dir else Path("reports/dossiers")
    out_path.mkdir(parents=True, exist_ok=True)
    generated = []

    for cid, name in rows:
        dossier = build_company_dossier(cid, db_path=db_path)
        md = format_dossier_markdown(dossier)
        clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        filename = out_path / f"company_{cid:03d}_{clean_name[:30]}.md"
        filename.write_text(md, encoding="utf-8")
        generated.append(str(filename))

    return generated

def _esc_tree(x):
    import html as _h
    if isinstance(x, str):
        return _h.escape(x)
    if isinstance(x, dict):
        return {k: _esc_tree(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_esc_tree(v) for v in x]
    return x


def format_dossier_print_html(dossier: dict) -> str:
    """Gera uma versao HTML desenhada para impressao A4 limpa e executiva (salvar como PDF)."""
    c = _esc_tree(dossier)
    fin = c.get("financials") or {}
    m = fin.get("metrics", {})
    d = fin.get("derived", {})

    rev_str = f"€ {m['revenue']['amount']:,.2f}" if "revenue" in m else "N/D"
    emp_str = str(int(m['employees']['amount'])) if "employees" in m else "N/D"
    rpe_str = f"€ {d['revenue_per_employee']:,.2f}" if "revenue_per_employee" in d else "N/D"
    l_ratio = f"{d['personnel_cost_ratio_pct']}%" if "personnel_cost_ratio_pct" in d else "N/D"

    status_label = {
        "meeting_agreed": "Reuniao / Cafe Agendado",
        "declined": "Contato Recusado",
        "pilot_agreed": "Piloto Fechado / em Andamento",
        "no_reply": "Sem Retorno",
        "no_contact": "Nao Contatado"
    }.get(c.get("funnel_status", "no_contact"), c.get("funnel_status", "no_contact"))

    ident_rows = "".join(
        f"<tr><td><strong>{i['type'].upper()}</strong></td><td><code>{i['value']}</code></td><td>{i['source']}</td></tr>"
        for i in c["identifiers"]
    )

    hyp_cards = "".join(
        f"""<div class="hyp-card">
            <h4>{idx}. {h['topic']}</h4>
            <p><strong>Hipotese Operacional:</strong> {h['hypothesis']}</p>
            <p class="question"><strong>Pergunta de Campo (Discovery):</strong> &ldquo;{h['validation_question']}&rdquo;</p>
        </div>"""
        for idx, h in enumerate(c["playbook"]["hypotheses"], start=1)
    )

    interactions_sec = ""
    if c.get("interactions"):
        int_rows = "".join(
            f"""<tr>
                <td>{it['occurred_on']}</td>
                <td><span class="badge">{it['outcome']}</span></td>
                <td>{it['role_of_contact'] or '—'}</td>
                <td>{it['stated_pain'] or '—'}</td>
                <td>{it['next_step'] or '—'}</td>
            </tr>"""
            for it in c["interactions"]
        )
        interactions_sec = f"""
        <h3>5. Historico de Contatos & Conversas de Campo</h3>
        <table class="grid-table">
            <thead><tr><th>Data</th><th>Desfecho</th><th>Cargo</th><th>Dor Identificada</th><th>Proximo Passo</th></tr></thead>
            <tbody>{int_rows}</tbody>
        </table>"""

    observations_sec = ""
    if c.get("observations"):
        obs_rows = "".join(
            f"<tr><td><strong>{o['field']}</strong></td><td>{o['value']}</td><td>{o['source']} ({o['date']})</td></tr>"
            for o in c["observations"]
        )
        observations_sec = f"""
        <h3>6. Informacoes Qualitativas Avulsas</h3>
        <table class="grid-table">
            <thead><tr><th>Topico</th><th>Informacao</th><th>Fonte</th></tr></thead>
            <tbody>{obs_rows}</tbody>
        </table>"""

    flags_html = "".join(f"<li>⚠️ {f}</li>" for f in c["data_quality_flags"]) if c["data_quality_flags"] else "<li>✅ Sem pendencias de integridade cadastral.</li>"

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Dossie Executivo - {c['legal_name']}</title>
<style>
@page {{ size: A4 portrait; margin: 15mm; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #16202e; margin: 0; padding: 20px; font-size: 11pt; line-height: 1.4; }}
.header {{ border-bottom: 2px solid #12263f; padding-bottom: 12px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: flex-start; }}
.header h1 {{ margin: 0; font-size: 18pt; color: #12263f; }}
.header .meta {{ font-size: 9pt; color: #556275; margin-top: 4px; }}
.badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; background: #e8eef8; color: #1f4e8c; font-weight: bold; font-size: 8.5pt; text-transform: uppercase; }}
h3 {{ font-size: 11pt; text-transform: uppercase; letter-spacing: 0.05em; color: #12263f; border-bottom: 1px solid #d0d7de; padding-bottom: 3px; margin: 14px 0 8px; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }}
.kpi {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; }}
.kpi .v {{ font-size: 13pt; font-weight: bold; color: #12263f; }}
.kpi .l {{ font-size: 7.5pt; text-transform: uppercase; color: #64748b; letter-spacing: 0.04em; }}
.grid-table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 9.5pt; }}
.grid-table th, .grid-table td {{ border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
.grid-table th {{ background: #f1f5f9; color: #475569; font-size: 8.5pt; text-transform: uppercase; }}
.hyp-card {{ background: #f8fafc; border-left: 3px solid #1f77b4; padding: 8px 12px; margin: 6px 0; border-radius: 4px; font-size: 9.5pt; }}
.hyp-card h4 {{ margin: 0 0 4px; font-size: 10pt; color: #0f3e69; }}
.hyp-card p {{ margin: 3px 0; }}
.hyp-card .question {{ color: #1e3a5f; font-style: italic; background: #edf4fb; padding: 4px 6px; border-radius: 3px; }}
ul.flags {{ margin: 0; padding-left: 18px; font-size: 9pt; color: #854d0e; }}
.print-actions {{ margin-bottom: 15px; }}
@media print {{
    .print-actions {{ display: none !important; }}
    body {{ padding: 0; }}
}}
</style>
</head>
<body>
<div class="print-actions">
    <button onclick="window.print()" style="padding: 8px 16px; background: #12263f; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">
        🖨️ Salvar como PDF / Imprimir
    </button>
    <span style="font-size: 12px; color: #666; margin-left: 10px;">Dica: Na janela de impressao, selecione <em>"Salvar como PDF"</em>.</span>
</div>

<div class="header">
    <div>
        <h1>{c['legal_name']}</h1>
        <div class="meta">ID #{c['company_id']} &bull; {c['address'] or 'Sede'}, {c['comune']} ({c['province']}) &bull; ATECO: {c['ateco_code']}</div>
    </div>
    <div>
        <span class="badge">{status_label}</span>
    </div>
</div>

<div class="kpis">
    <div class="kpi"><div class="v">{rev_str}</div><div class="l">Faturamento ({fin.get('fiscal_year', 'N/D')})</div></div>
    <div class="kpi"><div class="v">{emp_str}</div><div class="l">Colaboradores</div></div>
    <div class="kpi"><div class="v">{rpe_str}</div><div class="l">Receita / Funcionario</div></div>
    <div class="kpi"><div class="v">{l_ratio}</div><div class="l">Folha / Receita</div></div>
</div>

<h3>1. Identificadores Oficiais</h3>
<table class="grid-table">
    <thead><tr><th>Tipo</th><th>Codigo</th><th>Fonte Registrada</th></tr></thead>
    <tbody>{ident_rows}</tbody>
</table>

<h3>2. Limites de Confiabilidade (Data Quality Flags)</h3>
<ul class="flags">{flags_html}</ul>

<h3>3. Hipoteses Estrategicas & Perguntas de Descoberta</h3>
{hyp_cards}

{interactions_sec}

{observations_sec}

<div style="margin-top: 25px; border-top: 1px solid #e2e8f0; padding-top: 8px; font-size: 8pt; color: #94a3b8; text-align: center;">
    Piemonte Logistics & Industrial B2B Market Intel &bull; Fatos separados de hipoteses &bull; Documento confidencial
</div>
</body>
</html>"""
