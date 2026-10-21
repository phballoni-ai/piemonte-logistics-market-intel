import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv
from mintel.dossier import build_company_dossier, format_dossier_markdown, export_all_dossiers_markdown

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
