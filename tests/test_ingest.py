import pytest
from pathlib import Path
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv

def test_batch_ingest_with_rejections(tmp_path):
    db_file = tmp_path / "test_ingest.db"
    init_db(db_file)
    sample_csv = Path(__file__).resolve().parents[1] / "data" / "sample" / "pilot_synthetic_40.csv"
    assert sample_csv.exists()
    
    summary = ingest_companies_csv(sample_csv, db_path=db_file)
    assert summary["total_rows"] == 41
    assert summary["imported"] == 40
    assert summary["rejected"] == 1
    assert "checksum" in summary["rejections"][0]["reason"]
