"""Provedor `mock` -- padrão da demo (LLM_PROVEDOR não definido = mock, ver
.env.example). Não chama LLM nenhum: devolve um dos três planos
pré-gravados abaixo, escolhido pelo texto de alerta que os guardrails
determinísticos injetam no prompt (ver `_instrucao_guardrail_acwr` e
`_instrucao_guardrail_dor` em analisar_com_ia.py) -- não "entende" o resto
do prompt, só esse texto fixo.

Existe pra a demo sempre funcionar, mesmo sem Ollama rodando/baixado. A
revisão de coerência (Fase 11) sempre aprova aqui, porque os planos
pré-gravados já são escritos pra respeitar os guardrails -- reprovação de
verdade (Gemini/Ollama raciocinando sobre um plano ruim) só acontece com
um provedor que de fato lê o prompt. Ver README da demo."""

import json

_ALERTA_ACWR = "ALERTA OBRIGATÓRIO (carga semanal)"
_ALERTA_DOR = "ALERTA OBRIGATÓRIO (dor recente)"


def _treino(dia: str, tipo: str, km: float, minutos: float, pace: str, fc: str, motivo: str) -> dict:
    return {
        "dia_semana": dia,
        "descanso": False,
        "tipo_treino": tipo,
        "distancia_km": km,
        "duracao_min": minutos,
        "pace_alvo": pace,
        "fc_alvo": fc,
        "motivo": motivo,
    }


def _descanso(dia: str, motivo: str) -> dict:
    return {"dia_semana": dia, "descanso": True, "motivo": motivo}


_PLANO_NORMAL = {
    "dias": [
        _treino("Segunda", "Rodagem/Recuperação", 5.0, 32, "6:20-6:40", "128-138",
                "Rodagem leve pra abrir a semana sem acumular fadiga."),
        _descanso("Terça", "Descanso entre a rodagem de segunda e o treino de ritmo de quarta."),
        _treino("Quarta", "Ritmo", 6.0, 34, "5:50-6:05", "142-150",
                "Único treino de intensidade da semana -- regra de no máximo 1 por semana."),
        _descanso("Quinta", "Recuperação do treino de ritmo antes do longão de domingo."),
        _treino("Sexta", "Rodagem/Recuperação", 5.0, 33, "6:20-6:40", "128-138",
                "Rodagem leve, mantém volume sem se aproximar da intensidade de quarta."),
        _descanso("Sábado", "Descanso antes do longão."),
        _treino("Domingo", "Longão", 9.0, 62, "6:10-6:30", "132-145",
                "Progressão gradual de volume -- ACWR desta semana dentro da zona segura."),
    ],
    "estimativas_futuras": [
        {
            "tipo_treino": "Intervalado",
            "pace_alvo": "5:10-5:30 min/km",
            "fc_alvo": "155-165 bpm",
            "prazo_estimado": "provavelmente em 3-4 semanas, depois de 2-3 semanas seguidas de Ritmo sem dor",
            "nota": "Estimado a partir do pace de Ritmo já demonstrado -- ainda sem histórico de Intervalado.",
        },
    ],
    "logica_geral": (
        "[mock] Semana de progressão normal: 1 treino de ritmo, 1 longão com leve aumento de "
        "volume, resto em rodagem leve -- ACWR e dor dentro da faixa segura."
    ),
}

_PLANO_CAUTELOSO_ACWR = {
    "dias": [
        _treino("Segunda", "Rodagem/Recuperação", 4.0, 26, "6:30-6:50", "125-135",
                "Volume reduzido -- ACWR da semana acima da zona segura, prioridade é recuperação."),
        _descanso("Terça", "Descanso extra -- redução de carga total da semana."),
        _treino("Quarta", "Rodagem/Recuperação", 4.0, 26, "6:30-6:50", "125-135",
                "Sem treino de intensidade essa semana -- guardrail de ACWR alto."),
        _descanso("Quinta", "Descanso."),
        _descanso("Sexta", "Descanso extra -- mais um dia de recuperação do que o normal."),
        _descanso("Sábado", "Descanso antes do longão reduzido de domingo."),
        _treino("Domingo", "Longão", 7.0, 50, "6:30-6:50", "128-140",
                "Longão com volume reduzido em relação à semana anterior -- traz a carga de volta pra zona segura."),
    ],
    "estimativas_futuras": [],
    "logica_geral": (
        "[mock] ALERTA: ACWR desta semana acima da zona segura (0.8-1.3). Semana de redução de "
        "volume e intensidade, sem nenhum treino de Ritmo/Limiar/Intervalado/Tiro, priorizando "
        "recuperação até a carga normalizar."
    ),
}

_PLANO_CAUTELOSO_DOR = {
    "dias": [
        _treino("Segunda", "Rodagem/Recuperação", 4.0, 28, "6:40-7:00", "120-130",
                "Protocolo pós-canelite: dor recente registrada, só Rodagem/Recuperação ou Longão essa semana."),
        _descanso("Terça", "Descanso."),
        _treino("Quarta", "Rodagem/Recuperação", 4.0, 28, "6:40-7:00", "120-130",
                "Sem avanço de intensidade -- protocolo exige sessões consecutivas sem dor antes de progredir."),
        _descanso("Quinta", "Descanso."),
        _treino("Sexta", "Rodagem/Recuperação", 4.0, 28, "6:40-7:00", "120-130",
                "Terceira rodagem leve da semana -- monitorando se a dor volta antes de qualquer progressão."),
        _descanso("Sábado", "Descanso antes do longão."),
        _treino("Domingo", "Longão", 6.0, 45, "6:40-7:00", "125-135",
                "Longão em pace confortável, permitido pelo protocolo mesmo com dor recente registrada."),
    ],
    "estimativas_futuras": [],
    "logica_geral": (
        "[mock] ALERTA: dor recente registrada (nível >= 2). Protocolo de retomada pós-canelite: "
        "só Rodagem/Recuperação ou Longão essa semana, nenhum treino de intensidade, até haver "
        "sessões consecutivas sem dor."
    ),
}


def _escolher_plano(prompt: str) -> dict:
    # dor é o guardrail mais restritivo (trava intensidade mesmo se o ACWR
    # permitisse) -- mesma prioridade que um treinador real daria.
    if _ALERTA_DOR in prompt:
        return _PLANO_CAUTELOSO_DOR
    if _ALERTA_ACWR in prompt:
        return _PLANO_CAUTELOSO_ACWR
    return _PLANO_NORMAL


_REVISAO_APROVADA = {
    "coerente": True,
    "motivo": (
        "[mock] plano pré-gravado, escrito pra já respeitar os guardrails -- revisão de coerência "
        "de verdade (que pode reprovar um plano) só acontece com LLM_PROVEDOR=ollama ou gemini."
    ),
    "problemas": [],
}


def gerar_json(prompt: str, schema) -> str:
    if "coerente" in schema.model_fields:  # RevisaoCoerencia
        return json.dumps(_REVISAO_APROVADA)
    return json.dumps(_escolher_plano(prompt))


def contar_tokens(texto: str) -> int:
    return len(texto) // 4
