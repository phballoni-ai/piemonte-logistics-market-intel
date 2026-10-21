# Piemonte Logistics & Industrial B2B Market Intelligence

Sistema de inteligencia de mercado e prospeccao analitica voltado ao setor de **logistica e atacado de maquinario/pecas industriais** na regiao do Piemonte (foco na provincia de Torino e eixo Pinerolo-Orbassano-Rivalta).

O projeto implementa uma abordagem **evidence-first**:
1. **Fatos, fontes e datas estritamente separados de hipoteses.**
2. **Nenhum numero financeiro sem fonte (`source_id`) e ano fiscal de referencia.**
3. **Data Quality Flags:** Lacunas de dados e divergencias sao registradas como alertas de qualidade, sem inventar zeros ou suposicoes.
4. **Hipoteses Estrategicas Explicitas:** Dores operacionais e oportunidades de negocio sao rotuladas como hipoteses de trabalho, acompanhadas de perguntas nao-invasivas de validacao para conversas de campo (*discovery*).

---

## Estrutura do Projeto

```text
├── src/
│   └── mintel/
│       ├── __init__.py
│       ├── db.py           # Schema SQLite v2 & gerenciamento de conexoes
│       ├── validators.py   # Validacao de P.IVA (checksum italiano) e normalizacao ATECO
│       ├── ingest.py       # Ingestao atomica (SAVEPOINT) de lotes CSV com log de rejeicao
│       ├── dossier.py      # Gerador de Fichas de Inteligencia (Dossiers) & Hipoteses
│       └── cli.py          # Interface de linha de comando (CLI)
├── data/
│   └── sample/
│       └── pilot_synthetic_40.csv  # Dataset sintetico com 40 empresas + 1 caso de rejeicao
├── reports/
│   └── dossiers/           # Fichas individuais geradas em Markdown
└── tests/
    ├── test_db.py          # Testes unitarios do schema e integridade relacional
    ├── test_ingest.py      # Testes de ingestao atomica e relatorio de rejeicoes
    └── test_dossier.py     # Testes de extracao e formatacao de dossiers executivos
```

---

## Como Usar

### 1. Instalacao e Testes
```bash
git clone https://github.com/phballoni-ai/piemonte-logistics-market-intel.git
cd piemonte-logistics-market-intel
pip install -r requirements.txt

# Executar suite completa de testes
python -m pytest -q
```

### 2. Inicializar o Banco SQLite
```bash
PYTHONPATH=src python -m mintel.cli init
```

### 3. Ingerir Dados em Lote (CSV)
```bash
PYTHONPATH=src python -m mintel.cli ingest data/sample/pilot_synthetic_40.csv
```

### 4. Consultar Ficha de Inteligencia no Terminal
```bash
PYTHONPATH=src python -m mintel.cli dossier --id 1
```

### 5. Exportar Todos os Dossiers em Markdown
```bash
PYTHONPATH=src python -m mintel.cli export-dossiers --out reports/dossiers
```

---

## Playbooks e Hipoteses por Segmento

- **Logistica e Transporte Rodoviario (ATECO 49.41 / 52.10):**
  - *Hipotese 1 (Margem & Combustivel):* Pressao de custos em diesel e folha; oportunidade em roteirizacao dinamica, telemetria e reducao de rotas vazias (*backhaul*).
  - *Hipotese 2 (SLA & Visibilidade B2B):* Clientes industriais demandam visibilidade Just-in-Time; atrito em comprovacao digital de entrega (e-POD).
- **Atacado de Pecas e Maquinas Industriais (ATECO 46.62 / 46.69):**
  - *Hipotese 1 (Capital de Giro em Pecas):* Equilibrio entre estoque imobilizado em itens de baixo giro e risco de ruptura em componentes criticos (Curva A).
  - *Hipotese 2 (Digitalizacao B2B):* Tempo excessivo gasto por vendedores internos em cotacoes manuais repetitivas versus prospeccao ativa de contas industriais.
