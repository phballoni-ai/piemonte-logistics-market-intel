"""
Modulo de gestao de interacoes de campo e observacoes qualitativas.
Permite registrar:
- Historico de contatos e reunioes (outcome: meeting_agreed, declined, pilot_agreed, etc.)
- Notas pos-conversa (stated_pain, objection, next_step)
- Observacoes cadastrais avulsas adicionadas manualmente
"""
from datetime import date
from mintel.db import connect

VALID_OUTCOMES = ('no_reply', 'declined', 'meeting_agreed', 'pilot_agreed', 'other')

def log_interaction(company_id: int, occurred_on: str = None, channel: str = "field_meeting",
                    role_of_contact: str = None, stated_pain: str = None, objection: str = None,
                    outcome: str = "meeting_agreed", next_step: str = None, db_path=None) -> int:
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Outcome invalido: {outcome}. Opcoes: {VALID_OUTCOMES}")
    occurred_on = occurred_on or date.today().isoformat()
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO interactions (company_id, occurred_on, channel, role_of_contact, stated_pain, objection, outcome, next_step)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (company_id, occurred_on, channel, role_of_contact, stated_pain, objection, outcome, next_step)
    )
    iid = cur.lastrowid
    conn.commit()
    conn.close()
    return iid

def get_company_interactions(company_id: int, db_path=None) -> list:
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT interaction_id, occurred_on, channel, role_of_contact, stated_pain, objection, outcome, next_step
           FROM interactions WHERE company_id = ? ORDER BY occurred_on DESC, interaction_id DESC""",
        (company_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "occurred_on": r[1], "channel": r[2], "role_of_contact": r[3],
            "stated_pain": r[4], "objection": r[5], "outcome": r[6], "next_step": r[7]
        }
        for r in rows
    ]

def add_company_observation(company_id: int, field: str, value: str, reference_date: str = None,
                            source_name: str = "Anotacao de Campo", confidence: str = "high", db_path=None) -> int:
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute("SELECT source_id FROM data_sources WHERE name = ? LIMIT 1", (source_name,))
    row = cur.fetchone()
    if row:
        sid = row[0]
    else:
        cur.execute("INSERT INTO data_sources (name, source_type, retrieved_on) VALUES (?, 'field_conversation', ?)", (source_name, today))
        sid = cur.lastrowid
    cur.execute(
        """INSERT INTO observations (company_id, field, value, reference_date, source_id, confidence)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (company_id, field, value, reference_date or today, sid, confidence)
    )
    oid = cur.lastrowid
    conn.commit()
    conn.close()
    return oid

def get_company_observations(company_id: int, db_path=None) -> list:
    conn = connect(db_path) if db_path else connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT o.observation_id, o.field, o.value, o.reference_date, s.name, o.confidence
           FROM observations o
           JOIN data_sources s ON o.source_id = s.source_id
           WHERE o.company_id = ? ORDER BY o.observation_id DESC""",
        (company_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "field": r[1], "value": r[2], "date": r[3], "source": r[4], "confidence": r[5]}
        for r in rows
    ]
