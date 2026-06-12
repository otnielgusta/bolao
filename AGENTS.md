# AGENTS.md

Guia operacional para IAs e agentes de codigo trabalhando neste repositorio.

## Regras do ambiente

- Prefixe comandos de shell com `rtk`.
- Leia este arquivo e `docs/AI_CONTEXT.md` antes de alterar codigo.
- Preserve alteracoes nao relacionadas feitas por outra pessoa ou IA.
- Nao faca commit sem pedido explicito do usuario.
- Prefira mudancas pequenas, testaveis e alinhadas ao estilo existente.
- Use `apply_patch` para edicoes manuais de arquivos.
- Depois de alterar Python ou templates, rode validacoes relevantes:
  - `rtk uv run pytest`
  - `rtk uv run python -m compileall app`
  - `rtk uv run python -c "from app.templating import create_templates; create_templates().env.get_template('pools/detail.html'); print('template ok')"`

## Visao rapida

Este projeto e um bolao da Copa do Mundo 2026 em FastAPI + Jinja2 SSR, com PostgreSQL, SQLAlchemy async, Tailwind CDN e Alpine.js.

Pontos de negocio que nao devem divergir:

- Datas dos jogos ficam em UTC no banco.
- Datas exibidas ao usuario devem usar horario de Brasilia via `app.templating.local_strftime`.
- Prazo de palpite: 5 minutos antes de cada jogo, definido em `app/services/rules.py`.
- Pontuacao: `app/services/scoring.py`.
- Desempate do ranking: total, gabaritos de 10 pts, acertos de 7 pts, depois envio mais cedo da lista de palpites pontuados.
- Mata-mata ignora penaltis; o placar valido e tempo regulamentar + prorrogacao.

## Comandos comuns

```bash
rtk uv sync --all-groups
rtk docker compose up -d
rtk uv run alembic upgrade head
rtk uv run python seed.py
rtk uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
rtk uv run pytest
```

## Onde procurar

- `docs/AI_CONTEXT.md`: arquitetura, fluxos e regras.
- `docs/AI_HANDOFF.md`: checklist para passar trabalho entre IAs.
- `README.md`: setup humano resumido.
- `app/routers/`: rotas FastAPI.
- `app/templates/`: telas Jinja/Tailwind/Alpine.
- `app/services/`: regras de negocio, sync e pontuacao.
- `tests/`: cobertura atual.

