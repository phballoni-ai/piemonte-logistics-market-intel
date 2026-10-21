"""Ingestao em lote de empresas (CSV) para o SQLite.
Cada linha roda em SAVEPOINT: se falhar, nada dela fica gravado e o lote continua.
"""
import csv
from datetime import date
from mintel.db import connect
from mintel.validators import is_valid_piva_format, normalize_ateco

SEGMENTS = ("logistics", "wholesale_industrial_parts", "other")
SOURCE_TYPES = ("official_registry", "open_data", "company_website", "association_directory", "field_conversation", "other")


def _reject(summary, line, name, reason):
    summary["rejected"] += 1
    summary["rejections"].append({"line": line, "name": name, "reason": reason})


def ingest_companies_csv(csv_path, db_path=None):
    conn = connect(db_path) if db_path else connect()
    summary = {"total_rows": 0, "imported": 0, "rejected": 0, "rejections": []}
    sources = {}
    today = date.today().isoformat()
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            summary["total_rows"] += 1
            g = lambda k: (row.get(k) or "").strip()
            name, piva, seg, comune = g("legal_name"), g("partita_iva"), g("segment"), g("comune")
            if not name:
                _reject(summary, n, name, "razao social ausente"); continue
            if not comune or comune.lower() in ("none", "null", "nan"):
                _reject(summary, n, name, "comune ausente"); continue
            if piva and not is_valid_piva_format(piva):
                _reject(summary, n, name, f"P.IVA {piva} invalida (formato/checksum)"); continue
            if seg not in SEGMENTS:
                _reject(summary, n, name, f"segmento '{seg}' nao suportado"); continue
            stype = g("source_type") if g("source_type") in SOURCE_TYPES else "other"
            sname, surl = g("source_name") or "CSV import", g("source_url")
            conn.execute("SAVEPOINT row_sp")
            try:
                key = (sname, stype, surl)
                if key not in sources:
                    sources[key] = conn.execute(
                        "INSERT INTO data_sources(name,source_type,url,retrieved_on) VALUES (?,?,?,?)",
                        (sname, stype, surl or None, today)).lastrowid
                sid = sources[key]
                ateco = normalize_ateco(g("ateco_code")) if g("ateco_code") else None
                cid = conn.execute(
                    "INSERT INTO companies(legal_name,legal_form,comune,province,address,ateco_code,ateco_version,segment) VALUES (?,?,?,?,?,?,?,?)",
                    (name, g("legal_form") or None, comune, g("province") or None, g("address") or None,
                     ateco, g("ateco_version") or None, seg)).lastrowid
                ids = [("partita_iva", piva), ("codice_fiscale", g("codice_fiscale")), ("rea", g("rea"))]
                for t, v in ids:
                    if v:
                        conn.execute("INSERT INTO company_identifiers(company_id,id_type,value,source_id) VALUES (?,?,?,?)", (cid, t, v, sid))
                fy = g("fiscal_year")
                vals = [(k, g(c), d) for k, c, d in (("revenue", "revenue", "valore da CSV (definizione contabile a confirmar)"),
                        ("employees", "employees", "valore da CSV"), ("personnel_cost", "personnel_cost", "valore da CSV")) if g(c)]
                if fy and vals:
                    st = conn.execute("INSERT INTO financial_statements(company_id,fiscal_year,source_id) VALUES (?,?,?)", (cid, int(fy), sid)).lastrowid
                    for k, v, d in vals:
                        conn.execute("INSERT INTO financial_values(statement_id,item,amount,definition) VALUES (?,?,?,?)", (st, k, float(v), d))
                conn.execute("RELEASE row_sp")
                summary["imported"] += 1
            except Exception as e:
                conn.execute("ROLLBACK TO row_sp"); conn.execute("RELEASE row_sp")
                _reject(summary, n, name, f"{type(e).__name__}: {e}")
    conn.commit(); conn.close()
    return summary
