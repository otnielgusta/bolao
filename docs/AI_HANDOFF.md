# AI Handoff

Use este documento para passar o projeto entre IAs sem perder contexto.

## Estado base atual

Funcionalidades relevantes ja implementadas:

- Login, cadastro, convite e pools.
- Palpites por jogo com bloqueio 5 minutos antes do inicio.
- Ranking com criterios de desempate.
- Aba `Palpites` com visao geral agrupada por jogo e visao `Meus palpites`.
- Na aba `Jogos`, clicar no card abre os palpites daquele jogo.
- Aba `Regras` com pontuacao, prazo, mata-mata e desempate.
- Horarios corrigidos para Brasilia na exibicao.
- Sincronizacao com football-data.org e loop automatico de sync.

## Checklist ao assumir

1. Leia `AGENTS.md`.
2. Leia `docs/AI_CONTEXT.md`.
3. Rode `rtk git status --short`.
4. Se houver alteracoes pendentes, identifique se sao do usuario ou de outra IA antes de editar.
5. Localize o fluxo afetado com `rtk rg`.
6. Faça mudancas pequenas e rode testes.
7. Documente qualquer nova regra de negocio aqui ou em `docs/AI_CONTEXT.md`.

## Checklist antes de devolver

1. Rode os testes relevantes.
2. Rode `rtk uv run pytest` quando tocar regra, rota ou template importante.
3. Rode `rtk uv run python -m compileall app` quando tocar Python.
4. Carregue templates Jinja alterados quando tocar UI.
5. Confira `rtk git status --short`.
6. Informe arquivos alterados, validacoes executadas e qualquer pendencia.
7. So faca commit quando o usuario pedir explicitamente.

## Areas sensiveis

### Prazo de palpite

Use `app/services/rules.py`. Nao duplique `5`, `300` ou outro valor em rotas/templates.

### Timezone

Nao use `strftime` direto em `match_datetime` nos templates. Use `local_strftime`.

### Ranking

O ranking e calculado em `app/routers/pools.py`. Se mudar criterio, atualize:

- tabela em `app/templates/pools/_ranking_table.html`;
- aba `Regras` em `app/templates/pools/detail.html`;
- este handoff;
- testes, se o comportamento ficar coberto.

### Pontuacao

Fonte da verdade: `app/services/scoring.py`.

### Sincronizacao de resultados

Fonte da verdade: `app/services/sync.py`.
Tenha cuidado com a interpretacao de placar no mata-mata: penaltis nao entram.

## Mapa de mudancas comuns

- Alterar texto de regra exibida: `app/templates/pools/detail.html`, aba `rules`.
- Alterar prazo de palpite: `app/services/rules.py`.
- Alterar calculo de pontos: `app/services/scoring.py` e `tests/test_scoring.py`.
- Alterar ranking: `_build_ranking` em `app/routers/pools.py` e `_ranking_table.html`.
- Alterar card de jogo: `app/templates/matches/_match_card.html`.
- Alterar listagem geral de palpites: `app/templates/pools/_match_predictions.html` e bloco `predictions` em `detail.html`.
- Alterar timezone: `app/templating.py` e templates que formatam data.

## Comandos uteis

```bash
rtk git status --short
rtk rg -n "termo" app tests
rtk uv run pytest
rtk uv run python -m compileall app
rtk uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

