"""Camada de provedor de LLM -- existe só na demo (não no projeto original,
que sempre falou com o Gemini direto). `analisar_com_ia.py` chama apenas
`gerar_json(prompt, schema)` e `contar_tokens(texto)`; qual provedor está
por trás é decidido aqui, por `LLM_PROVEDOR` (ver .env.example):

    mock   -- padrão. Não chama LLM nenhum, devolve plano pré-gravado que
              reage aos guardrails. Sempre funciona, sem Docker extra.
    ollama -- modelo local rodando em container (docker compose --profile
              llm up), treino gerado de verdade, sem conta nem custo.
    gemini -- comportamento real do projeto original, exige GEMINI_API_KEY.

Cada provedor é um módulo com as duas funções acima (mesma interface,
sem precisar de classe/Protocol -- é o padrão que o resto do projeto já
usa pra "mecânica genérica", ver src/planilha.py e src/email_util.py)."""

import os
from types import ModuleType

_PROVEDORES = ("mock", "ollama", "gemini")


def obter_provedor() -> ModuleType:
    nome = os.environ.get("LLM_PROVEDOR", "mock")
    if nome not in _PROVEDORES:
        raise ValueError(f"LLM_PROVEDOR desconhecido: {nome!r} (use um de {_PROVEDORES})")
    if nome == "mock":
        from . import mock
        return mock
    if nome == "ollama":
        from . import ollama
        return ollama
    from . import gemini
    return gemini
