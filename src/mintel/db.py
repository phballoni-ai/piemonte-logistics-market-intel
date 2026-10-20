"""Schema SQLite v2. Principios:
1. Nenhum numero sem fonte (source_id) e data de referencia.
2. Fato publico, observacao de campo e hipotese ficam SEPARADOS.
3. Valores financeiros em formato "longo": ausente = linha inexistente (nunca 0 inventado).
4. Nenhum score de fraude. Inconsistencia vira 'data_quality_flags', nunca acusacao.
"""
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "local" / "market_intel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS data_sources (
    source_id     INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN
                  ('official_registry','open_data','company_website','association_directory','field_conversation','other')),
    url           TEXT,
    retrieved_on  TEXT NOT NULL,              -- ISO date da consulta
    terms_notes   TEXT                        -- licenca/termos de reuso verificados?
);

CREATE TABLE IF NOT EXISTS companies (
    company_id     INTEGER PRIMARY KEY,       -- ID interno, estavel
    legal_name     TEXT NOT NULL,
    legal_form     TEXT,                      -- SRL, SPA, SAS...
    comune         TEXT NOT NULL,
    province       TEXT,
    address        TEXT,
    ateco_code     TEXT,
    ateco_version  TEXT,                      -- ex: '2007' ou '2025' (confirmar!)
    segment        TEXT NOT NULL CHECK (segment IN ('logistics','wholesale_industrial_parts','other')),
    status         TEXT DEFAULT 'unverified' CHECK (status IN ('unverified','verified','inactive','excluded')),
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_identifiers (
    identifier_id  INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    id_type        TEXT NOT NULL CHECK (id_type IN ('codice_fiscale','partita_iva','rea')),
    value          TEXT NOT NULL,
    source_id      INTEGER REFERENCES data_sources(source_id),
    UNIQUE (id_type, value),
    UNIQUE (company_id, id_type)
);

-- Qualquer fato cadastral/publico avulso (campo, valor, periodo, fonte, confianca).
CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    field          TEXT NOT NULL,
    value          TEXT NOT NULL,
    reference_date TEXT,                      -- a que periodo o dado SE REFERE
    source_id      INTEGER NOT NULL REFERENCES data_sources(source_id),
    confidence     TEXT NOT NULL DEFAULT 'medium' CHECK (confidence IN ('low','medium','high'))
);

-- Demonstracoes financeiras com versao (correcoes/retificacoes nao sobrescrevem).
CREATE TABLE IF NOT EXISTS financial_statements (
    statement_id   INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    fiscal_year    INTEGER NOT NULL,
    statement_type TEXT CHECK (statement_type IN ('ordinario','abbreviato','micro','unknown')) DEFAULT 'unknown',
    version        INTEGER NOT NULL DEFAULT 1,
    currency       TEXT NOT NULL DEFAULT 'EUR',
    source_id      INTEGER NOT NULL REFERENCES data_sources(source_id),
    UNIQUE (company_id, fiscal_year, version)
);

CREATE TABLE IF NOT EXISTS financial_values (
    statement_id   INTEGER NOT NULL REFERENCES financial_statements(statement_id) ON DELETE CASCADE,
    item           TEXT NOT NULL,             -- ex: 'revenue','employees','personnel_cost','inventory'
    amount         REAL NOT NULL,
    definition     TEXT,                      -- qual voz contabil/fonte exata
    PRIMARY KEY (statement_id, item)
);

-- Sinais publicos verificaveis (certificacoes, vagas, unidades). Sao FATOS, nao interpretacao.
CREATE TABLE IF NOT EXISTS signals (
    signal_id      INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    signal_type    TEXT NOT NULL,             -- 'certification','job_posting','site_count','tracking_portal'...
    detail         TEXT,
    observed_on    TEXT NOT NULL,
    source_id      INTEGER NOT NULL REFERENCES data_sources(source_id)
);

-- Interacoes reais: o que foi DITO/OBSERVADO (fato da conversa).
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    occurred_on    TEXT NOT NULL,
    channel        TEXT,
    role_of_contact TEXT,                     -- cargo, nao dados pessoais
    stated_pain    TEXT,
    objection      TEXT,
    outcome        TEXT CHECK (outcome IN ('no_reply','declined','meeting_agreed','pilot_agreed','other')),
    next_step      TEXT
);

-- Hipoteses SEPARADAS dos fatos, com status de validacao.
CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id  INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    text           TEXT NOT NULL,
    based_on       TEXT,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','supported','refuted')),
    created_on     TEXT DEFAULT CURRENT_DATE
);

-- Sinaliza LIMITES de confiabilidade da analise (ex: dado antigo, campo ausente).
CREATE TABLE IF NOT EXISTS data_quality_flags (
    flag_id        INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    flag_type      TEXT NOT NULL,             -- 'stale_data','missing_fields','identity_unconfirmed'
    note           TEXT,
    created_on     TEXT DEFAULT CURRENT_DATE
);
"""


def connect(path=DEFAULT_DB):
    path = Path(path) if str(path) != ":memory:" else path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=DEFAULT_DB):
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


if __name__ == "__main__":
    init_db().close()
    print(f"Banco criado em {DEFAULT_DB}")
