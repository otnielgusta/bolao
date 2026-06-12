# AI Context

Contexto tecnico e de negocio para IAs que assumirem este projeto.

## Produto

Aplicacao web de bolao da Copa do Mundo FIFA 2026. Usuarios entram em pools, fazem palpites por jogo, acompanham ranking e visualizam palpites proprios e gerais.

## Stack

- FastAPI com renderizacao server-side via Jinja2.
- SQLAlchemy 2.x async com PostgreSQL via asyncpg.
- Alembic para migracoes.
- Autenticacao por cookie assinado com `itsdangerous`.
- TailwindCSS via CDN e Alpine.js via CDN.
- `uv` para dependencias e comandos Python.

## Estrutura principal

- `app/main.py`: cria a aplicacao, registra routers, inicia loop de autosync e expõe `/internal/sync`.
- `app/config.py`: settings via `pydantic-settings`, incluindo URL do banco, token football-data e token admin.
- `app/database.py`: engine e session async.
- `app/models/`: modelos SQLAlchemy.
- `app/routers/`: endpoints HTML e acoes POST.
- `app/services/scoring.py`: calculo de pontos por palpite.
- `app/services/rules.py`: constantes de regras compartilhadas, como prazo de palpite.
- `app/services/sync.py`: sincronizacao com football-data.org.
- `app/services/autosync.py`: loop automatico de sincronizacao quando jogos pendentes terminam.
- `app/templating.py`: criacao dos templates e filtros Jinja, incluindo timezone local.
- `app/templates/`: UI SSR em Jinja.
- `seed.py`: carga inicial dos jogos.
- `tests/`: testes de pontuacao e timezone.

## Modelo de dados

- `User`: usuario autenticado por email/senha, com `display_name`.
- `Pool`: bolao, dono e codigo de convite.
- `PoolMember`: associacao entre usuario e bolao.
- `Match`: jogo, times, horario UTC, fase, placar, flags de retroativo/finalizado e `external_id`.
- `Prediction`: palpite unico por usuario, bolao e jogo.

Invariante importante: `Prediction` tem unique constraint em `(user_id, pool_id, match_id)`.

## Fluxos de usuario

### Autenticacao

Rotas em `app/routers/auth.py`.

- `/auth/register`: cadastro.
- `/auth/login`: login.
- `/auth/logout`: remove cookie de sessao.
- `require_user`: dependencia usada por rotas privadas.

### Bolao

Rotas em `app/routers/pools.py`.

- `/pools`: dashboard dos boloes do usuario.
- `/pools/create`: criacao.
- `/pools/{pool_id}`: detalhe com abas:
  - `Jogos`: cards para palpitar; clicar no card abre palpites daquele jogo.
  - `Ranking`: tabela de classificacao.
  - `Palpites`: subtabs `Palpites geral` e `Meus palpites`.
  - `Regras`: explicacao de pontuacao, prazo, mata-mata e desempate.

### Palpites

Rota em `app/routers/predictions.py`.

- `POST /predictions`: cria ou atualiza palpite do usuario.
- Bloqueio padrao: `PREDICTION_DEADLINE_MINUTES` antes do inicio do jogo.
- Se `Match.allow_retroactive` estiver ativo, o dono pode permitir excecao ate o jogo encerrar.

### Admin

Rotas em `app/routers/admin.py`.

- Painel do dono do bolao.
- Alterna retroativo por jogo.
- Edita times de jogos nao finalizados.
- Registra resultado manualmente.
- Registra palpite em nome de membro, inclusive retroativo.

## Regras de negocio

### Pontuacao

Implementacao em `app/services/scoring.py`:

| Pontos | Regra |
| --- | --- |
| 10 | Placar exato |
| 7 | Vencedor/empate + saldo de gols |
| 5 | Vencedor/empate + gols de um dos times |
| 3 | Apenas vencedor/empate |
| 1 | Errou vencedor, mas acertou gols de um time |
| 0 | Nenhum criterio |

### Ranking

Implementacao em `_build_ranking` em `app/routers/pools.py`.

Ordem:

1. Maior pontuacao total.
2. Maior numero de acertos de 10 pontos.
3. Maior numero de acertos de 7 pontos.
4. Envio mais cedo da lista de palpites pontuados, representado pelo maior `submitted_at` entre os palpites pontuados do usuario.

### Datas e timezone

- Banco e sincronizacao trabalham em UTC.
- Exibicao para usuario deve usar Brasilia.
- Use `{{ value|local_strftime('%d/%m às %H:%M') }}` nos templates.
- No JavaScript, force `timeZone: 'America/Sao_Paulo'`.
- `app/templating.py` tem fallback BRT para Windows sem pacote `tzdata`.

### Mata-mata

Penaltis nao entram no placar do bolao. A sincronizacao usa `score.fullTime` da API, que representa tempo regulamentar + prorrogacao.

## Frontend

- UI esta em Jinja + Tailwind utility classes.
- Alpine controla interacoes locais, como countdown, toast e expansao de cards.
- Evite adicionar framework de frontend sem necessidade.
- Cards da aba `Jogos` usam `items-start` no grid e `self-start` no card para evitar que a expansao de um card estique a linha inteira.

## Sincronizacao externa

`app/services/sync.py` usa football-data.org:

- Busca jogos da competicao `WC`.
- Liga jogos por `external_id`, times da fase de grupos ou fase + kickoff no mata-mata.
- Atualiza horarios, times do mata-mata e resultados.
- Quando um jogo finaliza, recalcula pontuacao dos palpites.

`/internal/sync?token=...` força sync manual protegido por `ADMIN_TOKEN`.

## Testes e validacao

Comandos recomendados antes de encerrar trabalho:

```bash
rtk uv run pytest
rtk uv run python -m compileall app
rtk uv run python -c "from app.templating import create_templates; env=create_templates().env; env.get_template('pools/detail.html'); env.get_template('matches/_match_card.html'); print('templates ok')"
```

Quando alterar regras de pontuacao, atualize `tests/test_scoring.py`.
Quando alterar timezone, atualize `tests/test_templating.py`.

