"""Provedor `ollama` -- modelo rodando local, em container Docker (serviço
`ollama` do docker-compose.yml da demo). Saída estruturada via `format`
(JSON Schema), suportado pela API do Ollama desde a v0.5 -- mesma ideia do
`response_schema` do Gemini, reaproveitando o schema Pydantic que já
existe (PlanoSemanal/RevisaoCoerencia), sem duplicar regra nenhuma.

Sem chave de API, sem custo -- mas um modelo pequeno rodando em CPU erra
formato e coerência mais que o Gemini real, principalmente como revisor
(revisar_coerencia). Ver README.md pra o que validar antes de confiar no
resultado -- teste contra os quatro cenários de guardrail do seed
(SEED_CENARIO), não só contra o feliz caminho."""

import os

import httpx
from pydantic import BaseModel

MODELO_PADRAO = "qwen2.5:7b-instruct"

# CPU é lento pra um prompt com 4 semanas de histórico -- geração +
# revisão podem passar de 1 min cada, em máquina sem GPU.
TIMEOUT_SEG = 300


def _url() -> str:
    return os.environ.get("OLLAMA_URL", "http://ollama:11434")


def _modelo() -> str:
    return os.environ.get("OLLAMA_MODEL", MODELO_PADRAO)


def gerar_json(prompt: str, schema: type[BaseModel]) -> str:
    resposta = httpx.post(
        f"{_url()}/api/chat",
        json={
            "model": _modelo(),
            "messages": [{"role": "user", "content": prompt}],
            "format": schema.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=TIMEOUT_SEG,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    texto = (corpo.get("message") or {}).get("content")
    if not texto:
        raise RuntimeError(f"Ollama não devolveu conteúdo (resposta: {corpo}).")
    return texto


def contar_tokens(texto: str) -> int:
    """Ollama não expõe contagem de tokens antes de gerar -- estimativa
    por caracteres (~4 caracteres/token, regra prática pra
    português/inglês) só pra manter o mesmo guardrail de teto (Fase 10)
    que o provedor Gemini tem via count_tokens real."""
    return len(texto) // 4
