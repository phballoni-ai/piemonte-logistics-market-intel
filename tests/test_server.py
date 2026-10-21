import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mintel.db import init_db
from mintel.ingest import ingest_companies_csv
from mintel.server import MintelRequestHandler

CSV = Path(__file__).resolve().parents[1] / "data/sample/pilot_synthetic_40.csv"

def test_local_dashboard_upload_and_field_notes(tmp_path):
    db = tmp_path / "test.db"
    init_db(db).close()
    ingest_companies_csv(CSV, db_path=db)
    class LocalHandler(MintelRequestHandler):
        db_path = db
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    def get(path):
        with urllib.request.urlopen(base + path) as resp:
            return resp.read().decode()
    def post(path, data, content_type="application/json"):
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": content_type}, method="POST")
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    try:
        page = get("/")
        assert "upload-form" in page and "interaction-form" in page
        assert len(json.loads(get("/api/data"))) == 40
        result = post("/api/interaction", json.dumps({"company_id":1,"occurred_on":"2026-10-21","outcome":"meeting_agreed"}).encode())
        assert result["success"]
        result = post("/api/observation", json.dumps({"company_id":1,"field":"Frota","value":"Teste","source_name":"Demo"}).encode())
        assert result["success"]
        dossier = get("/dossier/1/print")
        assert "A4 portrait" in dossier and "Frota" in dossier
        single = CSV.read_bytes().splitlines()
        uploaded = post("/api/upload", b"\n".join(single[:2])+b"\n", "text/csv")
        assert uploaded["success"] and uploaded["summary"]["rejected"] == 1
    finally:
        server.shutdown()
        server.server_close()
