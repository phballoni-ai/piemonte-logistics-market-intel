import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv
from mintel.dossier import build_company_dossier, format_dossier_markdown, export_all_dossiers_markdown, format_dossier_print_html
from mintel.interactions import log_interaction, add_company_observation

CSV = Path(__file__).resolve().parents[1] / "data" / "sample" / "pilot_synthetic_40.csv"

def test_build_dossier_logistics(tmp_path):
    db = tmp_path / "t.db"
    init_db(db).close()
    ingest_companies_csv(CSV, db_path=db)

    d = build_company_dossier(1, db_path=db)
    assert d["legal_name"] == "Piemonte Logistica Test 01 S.r.l."
    assert d["segment"] == "logistics"
    assert d["financials"]["fiscal_year"] == 2024
    assert len(d["playbook"]["hypotheses"]) == 2

    md = format_dossier_markdown(d)
    assert "Dossier Executivo" in md
    assert "Piemonte Logistica Test 01 S.r.l." in md
    assert "Hipoteses de Abordagem" in md

def test_export_all_dossiers(tmp_path):
    db = tmp_path / "t.db"
    out_dir = tmp_path / "out"
    init_db(db).close()
    ingest_companies_csv(CSV, db_path=db)

    files = export_all_dossiers_markdown(db_path=db, output_dir=out_dir)
    assert len(files) == 40
    assert (out_dir / Path(files[0]).name).exists()

def test_dossier_interactions_and_print_html(tmp_path):
    db = tmp_path / "t.db"
    init_db(db).close()
    ingest_companies_csv(CSV, db_path=db)

    iid = log_interaction(
        company_id=1,
        occurred_on="2026-10-21",
        channel="field_meeting",
        role_of_contact="Direttore Logistica",
        stated_pain="Falta previsibilidade na malha",
        outcome="meeting_agreed",
        next_step="Demonstracao na terca",
        db_path=db
    )
    assert iid is not None

    oid = add_company_observation(
        company_id=1,
        field="Frota",
        value="20 caminhoes Scania",
        db_path=db
    )
    assert oid is not None

    d = build_company_dossier(1, db_path=db)
    assert d["funnel_status"] == "meeting_agreed"
    assert len(d["interactions"]) == 1
    assert len(d["observations"]) == 1

    html = format_dossier_print_html(d)
    assert "window.print()" in html
    assert "Direttore Logistica" in html
    assert "20 caminhoes Scania" in html
