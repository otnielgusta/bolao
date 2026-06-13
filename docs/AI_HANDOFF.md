# AI Handoff

Use este documento para passar o projeto entre IAs sem perder contexto.

## Estado base atual

Funcionalidades relevantes ja implementadas:

- Login, cadastro, convite e pools.
- Palpites por jogo com bloqueio 5 minutos antes do inicio.
- Ranking com criterios de desempate.
- Snapshots de ranking por jogo finalizado em `ranking_snapshots`.
- Aba `Rápido` para salvar varios palpites abertos de uma vez.
- Aba `Histórico` com evolucao de posicao e destaques.
- Aba `Atividade` com eventos recentes do bolao.
- Pagina publica somente leitura em `/pools/{pool_id}/public`.
- Perfil interno de participante em `/pools/{pool_id}/members/{member_id}`.
- Aba `Palpites` com visao geral agrupada por jogo e visao `Meus palpites`.
- Na aba `Jogos`, clicar no card abre os palpites daquele jogo.
- Aba `Regras` com pontuacao, prazo, mata-mata e desempate.
- Botoes de exportacao foram padronizados como `Copiar` texto formatado.
- Admin mostra saude do bolao: participacao aberta, membros sem palpites e jogos zerados.
- Horarios corrigidos para Brasilia na exibicao.
- Sincronizacao com football-data.org e loop automatico de sync.
- Fora do escopo atual por decisao do usuario: notificacoes internas, regras configuraveis por bolao e anti-esquecimento externo.

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

O ranking e calculado em `app/services/ranking.py`. Se mudar criterio, atualize:

- tabela em `app/templates/pools/_ranking_table.html`;
- aba `Regras` em `app/templates/pools/detail.html`;
- snapshots em `app/services/ranking.py` se a mudanca afetar historico;
- este handoff;
- testes, se o comportamento ficar coberto.

### Snapshots de ranking

Modelo: `app/models/ranking_snapshot.py`.
Migracao: `alembic/versions/b8f3a1c4d2e5_add_ranking_snapshots.py`.

Snapshots sao criados por:

- `app/routers/admin.py` quando resultado e registrado, palpite retroativo em jogo finalizado muda pontos, ou pontuacao e recalculada;
- `app/services/sync.py` quando o sync fecha jogo;
- `ensure_pool_snapshots` quando historico/perfil precisa preencher registros antigos ausentes.

### Copiar texto formatado

Use `copyText` e `copyExportText` definidos em `app/templates/base.html`.
Nao reintroduza botoes separados de WhatsApp/CSV. O fluxo atual e copiar o texto e colar onde quiser.

### Pontuacao

Fonte da verdade: `app/services/scoring.py`.

### Sincronizacao de resultados

Fonte da verdade: `app/services/sync.py`.
Tenha cuidado com a interpretacao de placar no mata-mata: penaltis nao entram.

## Mapa de mudancas comuns

- Alterar texto de regra exibida: `app/templates/pools/detail.html`, aba `rules`.
- Alterar prazo de palpite: `app/services/rules.py`.
- Alterar calculo de pontos: `app/services/scoring.py` e `tests/test_scoring.py`.
- Alterar ranking: `app/services/ranking.py` e `_ranking_table.html`.
- Alterar card de jogo: `app/templates/matches/_match_card.html`.
- Alterar listagem geral de palpites: `app/templates/pools/_match_predictions.html` e bloco `predictions` em `detail.html`.
- Alterar modo rapido: `app/templates/pools/detail.html` e `POST /predictions/bulk` em `app/routers/predictions.py`.
- Alterar pagina publica: `app/routers/pools.py` e `app/templates/pools/public.html`.
- Alterar perfil de participante: `app/routers/pools.py` e `app/templates/pools/member_profile.html`.
- Alterar saude do admin: `_build_pending_predictions` em `app/routers/admin.py` e `app/templates/admin/panel.html`.
- Alterar timezone: `app/templating.py` e templates que formatam data.

## Comandos uteis

```bash
rtk git status --short
rtk rg -n "termo" app tests
rtk uv run pytest
rtk uv run python -m compileall app
rtk uv run python -m compileall alembic
rtk uv run python -c "from app.templating import create_templates; env=create_templates().env; [env.get_template(t) for t in ['pools/detail.html','pools/public.html','pools/member_profile.html','matches/_match_card.html','admin/panel.html']]; print('templates ok')"
rtk uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
