"""Provedor `gemini` -- comportamento real do projeto original (não é o
padrão da demo, que é `mock`). Mesma lógica que estava antes direto em
analisar_com_ia.py, só extraída pra cá atrás da interface comum
(gerar_json/contar_tokens) -- ver docstring de src/llm/__init__.py.

Exige LLM_PROVEDOR=gemini e GEMINI_API_KEY no .env (gere em
aistudio.google.com/apikey, free tier)."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent.parent
MODELO_PADRAO = "gemini-3.5-flash"


def _cliente() -> tuple[genai.Client, str]:
    load_dotenv(ROOT / ".env")
    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    modelo = os.environ.get("GEMINI_MODEL", MODELO_PADRAO)
    return cliente, modelo


def gerar_json(prompt: str, schema: type[BaseModel]) -> str:
    """`response_schema` é config específica do Gemini (saída estruturada
    validada contra o schema Pydantic) -- fica contida aqui, então trocar
    de provedor nunca exige mudar o schema em si."""
    cliente, modelo = _cliente()
    resposta = cliente.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(
            # não usamos tools/function calling -- desliga o AFC padrão pra
            # não gerar o aviso "Direct use of AFC..." a cada chamada, sem
            # efeito nenhum no resultado.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    if not resposta.candidates:
        motivo = resposta.prompt_feedback.block_reason if resposta.prompt_feedback else "desconhecido"
        raise RuntimeError(f"Gemini bloqueou o prompt antes de gerar resposta (motivo: {motivo}).")
    finalizacao = resposta.candidates[0].finish_reason
    if finalizacao not in (types.FinishReason.STOP, None) or not resposta.text:
        raise RuntimeError(f"Gemini não completou a resposta (finish_reason={finalizacao}).")
    return resposta.text


def contar_tokens(texto: str) -> int:
    cliente, modelo = _cliente()
    return cliente.models.count_tokens(model=modelo, contents=texto).total_tokens
