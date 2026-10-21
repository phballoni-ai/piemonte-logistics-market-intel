"""
Módulo de Ingestão: Validação em lote e carga no SQLite.
Gera log de rejeições detalhado sem interromper o pipeline.
"""
import csv
import logging
from pathlib import Path
from mintel.db import connect
from mintel.validators import is_valid_piva_format, normalize_ateco

logger = logging.getLogger("mintel.ingest")


def ingest_companies_csv(csv_path, db_path=None):
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    
    summary = {
        "total_rows": 0,
        "imported": 0,
        "rejected": 0,
        "rejections": []
    }

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            summary["total_rows"] += 1
            legal_name = row.get("legal_name", "").strip()
            piva = row.get("partita_iva", "").strip()
            segment = row.get("segment", "").strip()
            comune = row.get("comune", "").strip()
            source_name = row.get("source_name", "CSV Batch Ingestion").strip()
            source_type = row.get("source_type", "other").strip()
            source_url = row.get("source_url", "").strip()
            
            # Validações estruturais (rejeições)
            if not legal_name:
                summary["rejected"] += 1
                summary["rejections"].append({"line": row_idx, "name": legal_name, "reason": "Razão social ausente"})
                continue
                
            if piva and not is_valid_piva_format(piva):
                summary["rejected"] += 1
                summary["rejections"].append({"line": row_idx, "name": legal_name, "reason": f"P.IVA {piva} com formato inválido (checksum/dígitos)"})
                continue
                
            if segment not in ("logistics", "wholesale_industrial_parts", "other"):
                summary["rejected"] += 1
                summary["rejections"].append({"line": row_idx, "name": legal_name, "reason": f"Segmento '{segment}' não suportado"})
                continue

            # Ingestão segura com transação
            try:
                # 1. Fonte
                cur.execute(
                    "INSERT INTO data_sources (name, source_type, url, retrieved_on) VALUES (?, ?, ?, CURRENT_DATE)",
                    (source_name, source_type, source_url)
                )
                source_id = cur.lastrowid

                # 2. Empresa
                ateco_raw = row.get("ateco_code", "")
                ateco_norm = normalize_ateco(ateco_raw) if ateco_raw else None
                cur.execute(
                    """INSERT INTO companies 
                    (legal_name, legal_form, comune, province, address, ateco_code, ateco_version, segment, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unverified')""",
                    (legal_name, row.get("legal_form"), comune, row.get("province", "TO"), 
                     row.get("address"), ateco_norm, row.get("ateco_version", "2007"), segment)
                )
                company_id = cur.lastrowid

                # 3. Identificadores (P.IVA / CF / REA)
                if piva:
                    cur.execute(
                        "INSERT INTO company_identifiers (company_id, id_type, value, source_id) VALUES (?, 'partita_iva', ?, ?)",
                        (company_id, piva, source_id)
                    )
                cf = row.get("codice_fiscale", "").strip()
                if cf and cf != piva:
                    cur.execute(
                        "INSERT INTO company_identifiers (company_id, id_type, value, source_id) VALUES (?, 'codice_fiscale', ?, ?)",
                        (company_id, cf, source_id)
                    )
                rea = row.get("rea", "").strip()
                if rea:
                    cur.execute(
                        "INSERT INTO company_identifiers (company_id, id_type, value, source_id) VALUES (?, 'rea', ?, ?)",
                        (company_id, rea, source_id)
                    )

                # 4. Dados Financeiros (se informados no CSV)
                fiscal_year = row.get("fiscal_year")
                revenue = row.get("revenue")
                employees = row.get("employees")
                if fiscal_year and (revenue or employees):
                    cur.execute(
                        "INSERT INTO financial_statements (company_id, fiscal_year, source_id) VALUES (?, ?, ?)",
                        (company_id, int(fiscal_year), source_id)
                    )
                    stmt_id = cur.lastrowid
                    if revenue:
                        cur.execute(
                            "INSERT INTO financial_values (statement_id, item, amount, definition) VALUES (?, 'revenue', ?, 'Conto Economico A1')",
                            (stmt_id, float(revenue))
                        )
                    if employees:
                        cur.execute(
                            "INSERT INTO financial_values (statement_id, item, amount, definition) VALUES (?, 'employees', ?, 'Dipendenti Medi Anno')",
                            (stmt_id, float(employees))
                        )

                summary["imported"] += 1
            except Exception as e:
                summary["rejected"] += 1
                summary["rejections"].append({"line": row_idx, "name": legal_name, "reason": str(e)})

    conn.commit()
    conn.close()
    return summary
