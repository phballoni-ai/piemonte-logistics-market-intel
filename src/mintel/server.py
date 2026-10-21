"""
Servidor Web Local do Piemonte Market Intel (somente 127.0.0.1, sem autenticacao).
1. Upload de CSV pelo navegador.
2. Painel com ranking e scores de prioridade.
3. Registro de interacoes e observacoes de campo.
4. Dossie A4 imprimivel (Salvar como PDF).
"""
import json
import os
import tempfile
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mintel.db import DEFAULT_DB, init_db
from mintel.dossier import build_company_dossier, format_dossier_print_html
from mintel.ingest import ingest_companies_csv
from mintel.interactions import add_company_observation, log_interaction
from mintel.report import build_report, collect


class MintelRequestHandler(BaseHTTPRequestHandler):
    db_path = None

    def _set_headers(self, status=HTTPStatus.OK, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(HTTPStatus.NO_CONTENT)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            html_path = build_report(db_path=self.db_path, out_path="/tmp/mintel_dashboard.html", live=True)
            with open(html_path, "rb") as f:
                content = f.read()
            self._set_headers(HTTPStatus.OK, "text/html")
            self.wfile.write(content)
            return

        if path == "/api/data":
            data = collect(db_path=self.db_path)
            self._set_headers(HTTPStatus.OK, "application/json")
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        if path.startswith("/dossier/") and path.endswith("/print"):
            try:
                parts = path.strip("/").split("/")
                cid = int(parts[1])
                d = build_company_dossier(cid, db_path=self.db_path)
                html = format_dossier_print_html(d)
                self._set_headers(HTTPStatus.OK, "text/html")
                self.wfile.write(html.encode("utf-8"))
                return
            except Exception as e:
                self._set_headers(HTTPStatus.NOT_FOUND, "text/plain")
                self.wfile.write(f"Erro: {e}".encode("utf-8"))
                return

        self._set_headers(HTTPStatus.NOT_FOUND, "text/plain")
        self.wfile.write(b"Nao encontrado")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        host = self.headers.get("Host", "").split(":")[0]
        origin = self.headers.get("Origin")
        if host not in ("localhost", "127.0.0.1") or (origin and urllib.parse.urlparse(origin).hostname not in ("localhost", "127.0.0.1")):
            self._set_headers(HTTPStatus.FORBIDDEN, "application/json")
            self.wfile.write(b'{"success":false,"error":"Origem nao permitida"}')
            return
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            content_length = 0
        if content_length < 1 or content_length > 2_000_000:
            self._set_headers(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "application/json")
            self.wfile.write(b'{"success":false,"error":"Arquivo deve ter entre 1 byte e 2 MB"}')
            return
        body = self.rfile.read(content_length)

        if path == "/api/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                csv_bytes = None
                if "multipart/form-data" in ctype:
                    boundary = ctype.split("boundary=")[1].encode()
                    parts = body.split(b"--" + boundary)
                    for p in parts:
                        if b"filename=" in p:
                            sub_parts = p.split(b"\r\n\r\n", 1)
                            if len(sub_parts) > 1:
                                csv_bytes = sub_parts[1].rsplit(b"\r\n", 1)[0]
                                break
                if not csv_bytes:
                    csv_bytes = body

                with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
                    tmp.write(csv_bytes)
                    tmp_name = tmp.name

                try:
                    summary = ingest_companies_csv(tmp_name, db_path=self.db_path)
                finally:
                    os.unlink(tmp_name)

                self._set_headers(HTTPStatus.OK, "application/json")
                self.wfile.write(json.dumps({"success": True, "summary": summary}).encode("utf-8"))
            except Exception as e:
                self._set_headers(HTTPStatus.BAD_REQUEST, "application/json")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        if path == "/api/interaction":
            try:
                payload = json.loads(body.decode("utf-8"))
                iid = log_interaction(
                    company_id=int(payload["company_id"]),
                    occurred_on=payload.get("occurred_on"),
                    channel=payload.get("channel", "field_meeting"),
                    role_of_contact=payload.get("role_of_contact"),
                    stated_pain=payload.get("stated_pain"),
                    objection=payload.get("objection"),
                    outcome=payload.get("outcome", "meeting_agreed"),
                    next_step=payload.get("next_step"),
                    db_path=self.db_path
                )
                self._set_headers(HTTPStatus.OK, "application/json")
                self.wfile.write(json.dumps({"success": True, "interaction_id": iid}).encode("utf-8"))
            except Exception as e:
                self._set_headers(HTTPStatus.BAD_REQUEST, "application/json")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        if path == "/api/observation":
            try:
                payload = json.loads(body.decode("utf-8"))
                oid = add_company_observation(
                    company_id=int(payload["company_id"]),
                    field=payload["field"],
                    value=payload["value"],
                    reference_date=payload.get("reference_date"),
                    source_name=payload.get("source_name", "Anotacao no painel"),
                    confidence=payload.get("confidence", "high"),
                    db_path=self.db_path
                )
                self._set_headers(HTTPStatus.OK, "application/json")
                self.wfile.write(json.dumps({"success": True, "observation_id": oid}).encode("utf-8"))
            except Exception as e:
                self._set_headers(HTTPStatus.BAD_REQUEST, "application/json")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        self._set_headers(HTTPStatus.NOT_FOUND, "text/plain")
        self.wfile.write(b"Endpoint nao encontrado")


def run_server(port=8000, db_path=None):
    handler = MintelRequestHandler
    handler.db_path = db_path or DEFAULT_DB
    init_db(handler.db_path).close()
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"\nServidor Piemonte Market Intel rodando em http://localhost:{port}")
    print("Pressione Ctrl+C para encerrar.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
