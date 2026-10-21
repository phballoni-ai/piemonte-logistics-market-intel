# Piemonte Logistics & Industrial B2B Market Intelligence

Protótipo de inteligência de mercado e prospecção analítica para **logística e atacado de peças industriais** na região do Piemonte (província de Torino, eixo Pinerolo-Orbassano-Rivalta).

Abordagem **evidence-first**:
1. Fatos, fontes e datas ficam separados de hipóteses.
2. Nenhum número financeiro entra sem fonte e ano fiscal.
3. Lacunas viram *data quality flags*; nunca se inventa zero.
4. Dores e oportunidades são **hipóteses a validar**, com perguntas de descoberta para a conversa de campo.

> **Os 40 registros de `data/sample/pilot_synthetic_40.csv` são integralmente fictícios.** Nenhuma interação de demonstração representa conversa real. Não há scraping, integração Telemaco ou acesso automatizado a registros oficiais.

## Estrutura

```text
src/mintel/
  db.py            schema SQLite e conexão
  validators.py    checksum de P.IVA e normalização ATECO
  ingest.py        ingestão em lote de CSV (cada linha em SAVEPOINT; rejeições listadas)
  interactions.py  contatos de campo (desfecho, dor, objeção, próximo passo) e observações com fonte
  dossier.py       dossiê por empresa (Markdown e HTML A4 imprimível)
  report.py        score de priorização e painel HTML
  server.py        servidor local (painel, upload de CSV, formulários de campo)
  cli.py           comandos
data/sample/       CSV sintético (40 empresas + 1 linha inválida de propósito)
tests/             testes automatizados
```

## Como rodar

```bash
git clone https://github.com/phballoni-ai/piemonte-logistics-market-intel.git
cd piemonte-logistics-market-intel
python -m pytest -q

PYTHONPATH=src python -m mintel.cli init
PYTHONPATH=src python -m mintel.cli ingest data/sample/pilot_synthetic_40.csv
PYTHONPATH=src python -m mintel.cli serve --port 8000     # abra http://localhost:8000
```

Outros comandos:

```bash
PYTHONPATH=src python -m mintel.cli report                 # painel estático em reports/dashboard.html (somente leitura)
PYTHONPATH=src python -m mintel.cli dossier --id 1         # dossiê no terminal
PYTHONPATH=src python -m mintel.cli export-dossiers        # um .md por empresa
```

## O painel local (`serve`)

- Ranking, filtros, gráfico e dossiê lateral por empresa.
- Importação de CSV pelo navegador.
- Formulários para registrar contato e observação (com fonte).
- Link "Salvar dossiê em PDF" (`/dossier/<id>/print`): abra e use *Imprimir > Salvar como PDF*.

## Score de priorização

Heurística de 0 a 100, **não é previsão de venda**: porte (40), equipe (20), intensidade de mão de obra (20) e completude dos dados (20). Tier A >= 80, B >= 55. As faixas são palpites iniciais e devem ser calibradas com resultados reais de conversas (`src/mintel/report.py`).

## Limites

- O servidor escuta apenas `127.0.0.1`, não tem autenticação e não deve ser exposto na internet.
- A importação é aditiva: P.IVA já importada é rejeitada, não sobrescrita.
- Checksum de P.IVA valida a forma, não a existência da empresa.
- Receita no CSV é tratada como informada pela fonte; a definição contábil exata deve ser confirmada na fonte real.

## Usar dados reais

O CSV de entrada precisa das colunas do arquivo de exemplo. Faça a ingestão em um banco novo (`--db caminho.db`) para não misturar com os dados fictícios, e troque a fonte (`source_name`, `source_type`, `source_url`) para a origem real.
