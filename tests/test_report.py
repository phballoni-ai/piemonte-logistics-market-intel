import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv
from mintel.report import build_report, collect

CSV = Path(__file__).resolve().parents[1] / "data" / "sample" / "pilot_synthetic_40.csv"

def _db(tmp_path):
    db = tmp_path / "t.db"; init_db(db).close(); ingest_companies_csv(CSV, db_path=db); return db

def test_scores_in_range_and_tiers(tmp_path):
    rows = collect(_db(tmp_path))
    assert len(rows) == 40
    assert all(0 <= r["score"] <= 100 and r["tier"] in "ABC" for r in rows)
    assert all(abs(sum(r["score_parts"].values()) - r["score"]) < 0.2 for r in rows)

def test_report_html(tmp_path):
    out = build_report(_db(tmp_path), out_path=tmp_path / "d.html")
    html = Path(out).read_text(encoding="utf-8")
    assert "DADOS SINTETICOS" in html and "Piemonte Logistica Test 01" in html
    assert "/*DATA*/null" not in html
