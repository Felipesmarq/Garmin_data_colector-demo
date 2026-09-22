FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /uvx /bin/

# Ambiente fora de /app de propósito: o docker-compose faz bind-mount da
# pasta inteira (.:/app) pra live-reload em dev -- um venv criado dentro
# de /app no build seria escondido pelo bind-mount do host em runtime.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

# Demo: `docker compose up` sozinho semeia o banco com dado sintético e
# imprime o que rodar em seguida (ver scripts/seed_demo.py) -- diferente do
# projeto original, que abria com a exploração da API real da Garmin
# (explore/inspect_garmin.py, não faz parte desta demo).
CMD ["python", "-m", "scripts.seed_demo"]
