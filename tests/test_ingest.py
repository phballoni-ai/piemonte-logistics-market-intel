import sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv

CSV = Path(__file__).resolve().parents[1] / "data" / "sample" / "pilot_synthetic_40.csv"

def test_batch_ingest_with_rejections(tmp_path):
    db = tmp_path / "t.db"; init_db(db).close()
    s = ingest_companies_csv(CSV, db_path=db)
    assert (s["total_rows"], s["imported"], s["rejected"]) == (41, 40, 1)
    assert "P.IVA" in s["rejections"][0]["reason"]
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 40
    assert c.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == 1

def test_failed_row_leaves_nothing_behind(tmp_path):
    db = tmp_path / "t.db"; init_db(db).close()
    bad = tmp_path / "bad.csv"
    bad.write_text(CSV.read_text().splitlines()[0] + "\n" + CSV.read_text().splitlines()[1].replace(",2024,", ",20x4,") + "\n")
    s = ingest_companies_csv(bad, db_path=db)
    assert s["imported"] == 0 and s["rejected"] == 1
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0
