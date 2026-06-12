# Bolão Copa do Mundo 2026

Sistema web de bolão para a Copa do Mundo FIFA 2026.

## Stack

- **Backend:** FastAPI + Jinja2 (SSR)
- **ORM:** SQLAlchemy 2.x async + asyncpg
- **Banco:** PostgreSQL
- **Migrações:** Alembic
- **Auth:** Sessões via cookie (itsdangerous)
- **Frontend:** TailwindCSS CDN + Alpine.js CDN

## Setup Local

### Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL (ou Docker)

### 1. Subir o banco

```bash
docker compose up -d
```

### 2. Instalar dependências

```bash
uv sync --all-groups
```

### 3. Configurar ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais se necessário
```

### 4. Rodar migrações

```bash
make migration msg="initial"
make migrate
```

### 5. Popular jogos

```bash
make seed
```

### 6. Iniciar servidor

```bash
make dev
```

Acesse http://localhost:8000

## Testes

```bash
make test
```

## Documentacao para IAs

Este repositorio tem documentos para handoff entre agentes:

- `AGENTS.md`: instrucoes operacionais para IAs.
- `docs/AI_CONTEXT.md`: arquitetura, fluxos e regras de negocio.
- `docs/AI_HANDOFF.md`: checklist para assumir ou entregar trabalho.

## Regras de Pontuação

| Pontos | Critério |
|--------|----------|
| 10 | Placar exato |
| 7 | Vencedor/empate + saldo de gols correto |
| 5 | Vencedor/empate + gols de um time correto |
| 3 | Apenas vencedor/empate correto |
| 1 | Errou vencedor, mas acertou gols de um time |
| 0 | Nenhum critério |
