# Piemonte Logistics Market Intel (piloto, privado)

Base de dados *evidence-first* para o piloto de ~40 empresas de **logistica** e **atacado de pecas/componentes industriais** na regiao de Pinerolo/Torino.

## Principios
1. **Nenhum numero sem fonte e data.** Todo valor aponta para `data_sources`.
2. **Fato, observacao de campo e hipotese ficam separados** (`observations`/`signals`, `interactions`, `hypotheses`).
3. **Dado ausente nao vira zero.** Valores financeiros ficam em formato longo; sem dado = sem linha.
4. **Sem score de fraude e sem rotulos sobre empresas.** Inconsistencias viram `data_quality_flags` (limite de confiabilidade da analise).
5. **Sem dados pessoais de dirigentes** nesta fase. Interacoes guardam o *cargo*, nao o nome.
6. **Dados reais ficam fora do Git** (ver `.gitignore`). O repositorio so tem codigo, schema e dados ficticios.

## Como rodar
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
python src/mintel/db.py   # cria data/local/market_intel.db
```

## Limites conhecidos
- `is_valid_piva_format` valida so a *forma* (11 digitos + digito verificador), nao a existencia da empresa.
- Codigos ATECO: a Italia atualizou a classificacao (alinhada a NACE Rev. 2.1). Confirmar a versao vigente antes de filtrar; o campo `ateco_version` existe para isso.
- SQLite e para o piloto local. O `.db` nao deve ser editado em simultaneo por duas pessoas via pasta sincronizada; migrar para PostgreSQL se a colaboracao crescer.
- Antes de qualquer revenda de dados: checar termos de cada fonte e GDPR.

## Roadmap
- [x] Bloco 1: schema + validadores + testes
- [ ] Bloco 2: importacao de CSV (template ficticio) com validacao e relatorio de rejeicoes
- [ ] Bloco 3: relatorio de qualidade/cobertura dos dados (sem score de propensao ainda)
