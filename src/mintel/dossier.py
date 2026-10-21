"""
Modulo de Inteligencia de Contas (Dossier e Hipoteses de Abordagem).
Gera fichas estruturadas separando estritamente:
- Fatos cadastrais e economicos com fonte
- Data quality flags (lacunas e limites dos dados)
- Hipoteses de dor e oportunidade (claramente rotuladas como hipoteses)
- Perguntas de validacao para conversa de campo (discovery)
"""
from pathlib import Path
from mintel.db import connect

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

    # 1. Dados cadastrais da empresa
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

    # 2. Identificadores (P.IVA, CF, REA)
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

    # 3. Demonstrativo financeiro mais recente
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
        # Indicadores derivados simples (se dados disponiveis)
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

    # 4. Data Quality Flags
    flags = []
    if not any(i["type"] == "partita_iva" for i in company["identifiers"]):
        flags.append("P.IVA ausente no cadastro")
    if not company.get("financials"):
        flags.append("Nenhum balanco/dado financeiro registrado ainda")
    if company.get("status") == "unverified":
        flags.append("Cadastro preliminar (ainda nao verificado no Registro Imprese oficial)")
    company["data_quality_flags"] = flags

    # 5. Playbook & Hipoteses
    seg = company.get("segment") or "other"
    playbook = SEGMENT_PLAYBOOKS.get(seg, SEGMENT_PLAYBOOKS["other"])
    company["playbook"] = playbook

    conn.close()
    return company


def format_dossier_markdown(dossier: dict) -> str:
    """Renderiza a ficha executiva em Markdown profissional."""
    c = dossier
    p_title = c["playbook"]["title"]
    lines = [
        f"# Dossier Executivo: {c['legal_name']}",
        f"*ID Interno:* #{c['company_id']} | *Segmento:* {p_title} | *Status:* `{c['status']}`",
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
        lines.append(f"**Pergunta de Descoberta (Campo):** *\"{h['validation_question']}\"*\n")

    return "\n".join(lines)


def export_all_dossiers_markdown(db_path=None, output_dir=None) -> list:
    """Gera fichas individuais para todas as empresas do banco."""
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
