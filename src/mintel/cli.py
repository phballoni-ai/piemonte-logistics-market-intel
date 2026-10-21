"""
CLI do Piemonte Logistics Market Intel.
Comandos faceis para:
- Inicializar banco: python -m mintel.cli init
- Ingerir dados: python -m mintel.cli ingest <caminho_csv>
- Gerar dossier de uma empresa: python -m mintel.cli dossier --id 1
- Exportar todos os dossiers em Markdown: python -m mintel.cli export-dossiers
- Gerar dashboard visual HTML: python -m mintel.cli report
"""
import argparse
import sys
from pathlib import Path
from mintel.db import init_db
from mintel.report import build_report
from mintel.dossier import build_company_dossier, format_dossier_markdown, export_all_dossiers_markdown


def main():
    parser = argparse.ArgumentParser(description="Piemonte Market Intel CLI")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponiveis")

    # init
    p_init = subparsers.add_parser("init", help="Inicializa o banco SQLite v2")
    p_init.add_argument("--db", default=None, help="Caminho do arquivo SQLite")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingere lote de empresas via CSV")
    p_ingest.add_argument("csv_path", help="Caminho do arquivo CSV")
    p_ingest.add_argument("--db", default=None, help="Caminho do arquivo SQLite")

    # dossier
    p_dossier = subparsers.add_parser("dossier", help="Exibe a ficha de inteligencia de uma empresa")
    p_dossier.add_argument("--id", type=int, required=True, help="ID da empresa")
    p_dossier.add_argument("--db", default=None, help="Caminho do arquivo SQLite")

    # export-dossiers
    p_export = subparsers.add_parser("export-dossiers", help="Exporta fichas Markdown de todas as empresas")
    p_export.add_argument("--db", default=None, help="Caminho do arquivo SQLite")
    p_export.add_argument("--out", default="reports/dossiers", help="Diretorio de saida")

    # report
    p_rep = subparsers.add_parser("report", help="Gera o painel visual HTML")
    p_rep.add_argument("--db", default=None, help="Caminho do arquivo SQLite")
    p_rep.add_argument("--out", default="reports/dashboard.html", help="Arquivo HTML de saida")

    args = parser.parse_args()

    if args.command == "init":
        init_db(args.db).close()
        print("Banco SQLite inicializado com sucesso.")
    elif args.command == "ingest":
        summary = ingest_companies_csv(args.csv_path, db_path=args.db)
        print(f"Total: {summary['total_rows']} | Importadas: {summary['imported']} | Rejeitadas: {summary['rejected']}")
        for r in summary["rejections"]:
            print(f"  [Linha {r['line']}] {r['name']}: {r['reason']}")
    elif args.command == "dossier":
        dossier = build_company_dossier(args.id, db_path=args.db)
        print(format_dossier_markdown(dossier))
    elif args.command == "export-dossiers":
        files = export_all_dossiers_markdown(db_path=args.db, output_dir=args.out)
        print(f"Sucesso: {len(files)} dossiers gerados na pasta '{args.out}'.")
    elif args.command == "report":
        print("Painel gerado em:", build_report(db_path=args.db, out_path=args.out))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
