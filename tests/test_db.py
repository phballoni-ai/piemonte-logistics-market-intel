import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pytest
from mintel.db import init_db
from mintel.validators import is_valid_piva_format, normalize_ateco, piva_check_digit


def _db():
    return init_db(":memory:")


def _seed(conn):
    conn.execute("INSERT INTO data_sources(source_id,name,source_type,retrieved_on) VALUES (1,'teste','other','2026-01-01')")
    conn.execute("INSERT INTO companies(company_id,legal_name,comune,segment) VALUES (1,'Fittizia SRL','Pinerolo','logistics')")


def test_piva_checksum():
    base = "1234567890"
    valid = base + str(piva_check_digit(base))
    assert is_valid_piva_format(valid)
    assert not is_valid_piva_format(base + str((piva_check_digit(base) + 1) % 10))
    assert not is_valid_piva_format("123")


def test_ateco_normalization():
    assert normalize_ateco("4941") == "49.41"
    assert normalize_ateco("49.41.00") == "49.41"


def test_missing_value_is_not_zero_and_versions_allowed():
    c = _db(); _seed(c)
    c.execute("INSERT INTO financial_statements(company_id,fiscal_year,version,source_id) VALUES (1,2024,1,1)")
    c.execute("INSERT INTO financial_statements(company_id,fiscal_year,version,source_id) VALUES (1,2024,2,1)")
    assert c.execute("SELECT COUNT(*) FROM financial_values").fetchone()[0] == 0


def test_duplicate_identifier_rejected():
    c = _db(); _seed(c)
    c.execute("INSERT INTO company_identifiers(company_id,id_type,value) VALUES (1,'partita_iva','12345678903')")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO company_identifiers(company_id,id_type,value) VALUES (1,'partita_iva','12345678903')")


def test_observation_requires_source():
    c = _db(); _seed(c)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO observations(company_id,field,value) VALUES (1,'x','y')")
