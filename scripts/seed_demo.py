"""Seed sintético da demo -- substitui a Fase 2 (extract/garmin.py) por dado
gerado, direto nas mesmas tabelas de staging, reaproveitando as mesmas
funções `carregar()` de load_atividades.py/load_recuperacao.py que o
pipeline real usa (upsert idempotente, mesmo schema, zero duplicação de
lógica de banco). Nenhum dado do Garmin de ninguém entra aqui.

12 semanas terminando na última semana ISO completa antes de hoje (não
inclui a semana corrente, que estaria parcial e distorceria o ACWR da
"semana mais recente" -- ver vw_resumo_semanal). Roda toda vez que o
container sobe (CMD do Dockerfile); se o banco já tem atividades, pula
(idempotente) -- pra recriar do zero: `docker compose down -v && docker
compose up`, ou `SEED_FORCAR=true` pra semear de novo por cima.

SEED_CENARIO (.env, padrão "ambos") controla a semana mais recente (S12),
onde os dois guardrails determinísticos de analisar_com_ia.py podem
disparar:
    ambos  -- pico de volume (ACWR > 1.5) E dor registrada no treino mais
              recente (nível 3) -- os dois guardrails juntos, cenário mais
              rico pra demonstrar o sistema.
    acwr   -- só o pico de volume.
    dor    -- só a dor recente, volume normal.
    normal -- semana igual às anteriores, nenhum guardrail dispara.
As semanas 1-11 são iguais em qualquer cenário (progressão de base
gradual, sem pico) -- só a mais recente muda.
"""

import os
from datetime import date, datetime, timedelta

from src.db import conectar
from src.load.load_atividades import carregar as carregar_atividades
from src.load.load_recuperacao import carregar as carregar_recuperacao
from src.tempo import hoje_brt

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# tipo_treino -> perfil fisiológico (ver CASE_DO_PROJETO_1.md seção 6.1 e a
# CASE WHEN de tipo_treino em schema.sql -- estas frações de zona de FC e
# efeito anaeróbico são o que faz cada sessão classificar como o tipo
# pretendido). Sem Intervalado/Tiro de propósito -- ficam só como
# "estimativas_futuras" no plano (ver src/llm/mock.py), igual um corredor
# real em retomada que ainda não chegou lá.
PERFIS = {
    "Rodagem/Recuperação": dict(pace=6.5, fc=133, baixa=.90, media=.10, alta=.00, aerobico=2.2, anaerobico=0.2, label="RECOVERY"),
    "Longão":               dict(pace=6.3, fc=138, baixa=.88, media=.10, alta=.02, aerobico=3.4, anaerobico=0.3, label="AEROBIC_BASE"),
    "Ritmo":                dict(pace=5.95, fc=146, baixa=.40, media=.35, alta=.25, aerobico=3.6, anaerobico=0.9, label="TEMPO_EFFECT"),
    "Limiar":               dict(pace=5.65, fc=155, baixa=.25, media=.30, alta=.45, aerobico=3.8, anaerobico=1.1, label="LACTATE_THRESHOLD"),
}

# (dia_offset 0=Segunda..6=Domingo, tipo_treino, km) -- semanas 1 a 11 são
# fixas em qualquer cenário; só a semana 12 varia (ver _semana_12 abaixo).
SEMANAS_1_A_11 = [
    [(0, "Rodagem/Recuperação", 4.0), (2, "Rodagem/Recuperação", 4.0), (4, "Rodagem/Recuperação", 4.0), (6, "Longão", 6.0)],
    [(0, "Rodagem/Recuperação", 4.0), (2, "Rodagem/Recuperação", 4.5), (4, "Rodagem/Recuperação", 4.0), (6, "Longão", 7.0)],
    [(0, "Rodagem/Recuperação", 4.5), (2, "Rodagem/Recuperação", 4.5), (4, "Rodagem/Recuperação", 4.5), (6, "Longão", 7.5)],
    [(0, "Rodagem/Recuperação", 4.5), (2, "Rodagem/Recuperação", 4.5), (4, "Rodagem/Recuperação", 4.5), (6, "Longão", 8.0)],
    [(0, "Rodagem/Recuperação", 4.5), (2, "Ritmo", 5.0), (4, "Rodagem/Recuperação", 4.5), (6, "Longão", 8.0)],
    [(0, "Rodagem/Recuperação", 4.5), (2, "Ritmo", 5.5), (4, "Rodagem/Recuperação", 4.5), (6, "Longão", 8.5)],
    [(0, "Rodagem/Recuperação", 5.0), (2, "Ritmo", 5.5), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 8.5)],
    [(0, "Rodagem/Recuperação", 5.0), (2, "Limiar", 5.5), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 9.0)],
    [(0, "Rodagem/Recuperação", 5.0), (2, "Ritmo", 6.0), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 9.0)],
    [(0, "Rodagem/Recuperação", 5.0), (2, "Limiar", 6.0), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 9.0)],
    [(0, "Rodagem/Recuperação", 5.0), (2, "Ritmo", 6.0), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 9.5)],
]

_SEMANA_12_NORMAL = [(0, "Rodagem/Recuperação", 5.0), (2, "Ritmo", 6.0), (4, "Rodagem/Recuperação", 5.0), (6, "Longão", 9.5)]
# Pico de ACWR: mais sessões na semana (5 em vez de 4, sem descanso entre
# quarta e sábado) + longão bem maior -- overreach real costuma ser "não
# respeitou os dias de descanso", não só "um treino gigante isolado". Km de
# Rodagem/Recuperação continua <=5.0 (mesmo de outras semanas) de propósito:
# 6.0km nesse pace passa de 35min e vw_sessoes classificaria como Longão
# (baixa>=85% + duração>=35min, ver schema.sql) -- confirmado testando
# contra Postgres real antes de fechar os números (ver memória "validar
# antes de confiar").
_SEMANA_12_PICO = [
    (0, "Rodagem/Recuperação", 5.0),
    (2, "Ritmo", 7.0),
    (3, "Rodagem/Recuperação", 5.0),  # sessão extra de quinta -- sem descanso depois do ritmo de quarta
    (4, "Rodagem/Recuperação", 5.0),
    (5, "Rodagem/Recuperação", 5.0),  # sessão extra de sábado -- sem descanso antes do longão
    (6, "Longão", 19.0),
]

CENARIOS = {
    # (semana 12 = pico de volume?, dor no treino mais recente)
    "ambos": (True, 3),
    "acwr": (True, None),
    "dor": (False, 3),
    "normal": (False, None),
}

# dor leve (abaixo do limiar de guardrail, que é >=2) em algumas sessões
# passadas -- realismo: a aba "Dor" não fica vazia fora do cenário
# principal. Índice = posição da sessão na lista cronológica completa.
DOR_LEVE_NOS_INDICES = {6: 1, 15: 0, 24: 1, 33: 1}


def _semana_12(pico: bool) -> list[tuple[int, str, float]]:
    return _SEMANA_12_PICO if pico else _SEMANA_12_NORMAL


def _zonas_fc(perfil: dict, duracao_seg: float) -> tuple[float, float, float, float, float]:
    baixa, media, alta = perfil["baixa"] * duracao_seg, perfil["media"] * duracao_seg, perfil["alta"] * duracao_seg
    return baixa / 2, baixa / 2, media, alta / 2, alta / 2


def _atividade(activity_id: int, dia: date, hora: tuple[int, int], tipo: str, km: float) -> dict:
    perfil = PERFIS[tipo]
    duracao_min = km * perfil["pace"]
    duracao_seg = duracao_min * 60
    z1, z2, z3, z4, z5 = _zonas_fc(perfil, duracao_seg)
    nomes = {
        "Rodagem/Recuperação": "Rodagem leve",
        "Longão": "Longão de domingo",
        "Ritmo": "Treino de ritmo",
        "Limiar": "Treino de limiar",
    }
    return {
        "activity_id": activity_id,
        "activity_uuid": f"demo-{activity_id}",
        "data": dia,
        "hora_inicio": datetime.combine(dia, datetime.min.time()).replace(hour=hora[0], minute=hora[1]),
        "nome": nomes[tipo],
        "tipo": "running",
        "distancia_m": round(km * 1000, 1),
        "duracao_seg": round(duracao_seg, 1),
        "duracao_movimento_seg": round(duracao_seg * 0.97, 1),
        "velocidade_media_mps": round((km * 1000) / duracao_seg, 3),
        "velocidade_maxima_mps": round((km * 1000) / duracao_seg * 1.25, 3),
        "velocidade_ajustada_grade_mps": round((km * 1000) / duracao_seg * 1.02, 3),
        "fc_media": perfil["fc"],
        "fc_maxima": perfil["fc"] + 12,
        "cadencia_media": 170.0,
        "cadencia_maxima": 186.0,
        "ganho_elevacao": 35.0,
        "perda_elevacao": 35.0,
        "elevacao_media": 710.0,
        "elevacao_minima": 690.0,
        "elevacao_maxima": 735.0,
        "potencia_media": 260.0,
        "potencia_maxima": 340.0,
        "potencia_normalizada": 265.0,
        "efeito_treino_aerobico": perfil["aerobico"],
        "efeito_treino_anaerobico": perfil["anaerobico"],
        "efeito_treino_label": perfil["label"],
        "tempo_zona_fc_1": round(z1, 1),
        "tempo_zona_fc_2": round(z2, 1),
        "tempo_zona_fc_3": round(z3, 1),
        "tempo_zona_fc_4": round(z4, 1),
        "tempo_zona_fc_5": round(z5, 1),
        "tempo_contato_solo_medio": 265.0,
        "comprimento_passada_medio": 1.05,
        "oscilacao_vertical_media": 8.8,
        "razao_vertical_media": 7.2,
        "fastest_split_1km_seg": round(perfil["pace"] * 60 * 0.95, 1),
        "fastest_split_1milha_seg": round(perfil["pace"] * 60 * 1.609 * 0.95, 1),
        "minutos_intensidade_moderada": round(duracao_min * 0.6),
        "minutos_intensidade_vigorosa": round(duracao_min * (0.35 if tipo in ("Ritmo", "Limiar") else 0.0)),
        "body_battery_variacao": -round(duracao_min * 0.5),
        "calorias": round(km * 65),
    }


def _gerar_atividades(fim_dados: date, pico_semana_12: bool) -> list[dict]:
    semanas = SEMANAS_1_A_11 + [_semana_12(pico_semana_12)]
    segunda_semana_12 = fim_dados - timedelta(days=6)
    atividades = []
    activity_id = 900_000_001
    for i_semana, sessoes in enumerate(semanas):
        segunda = segunda_semana_12 - timedelta(weeks=(11 - i_semana))
        for dia_offset, tipo, km in sessoes:
            dia = segunda + timedelta(days=dia_offset)
            hora = (7, 30) if tipo == "Longão" else (6, 30)
            atividades.append(_atividade(activity_id, dia, hora, tipo, km))
            activity_id += 1
    return atividades


def _gerar_recuperacao(inicio: date, fim: date, pico_semana_12: bool) -> list[dict]:
    segunda_semana_12 = fim - timedelta(days=6)
    dias = []
    d = inicio
    while d <= fim:
        # semana do pico: leve queda de recuperação -- consistente com a
        # carga maior (não é o guardrail em si, que é só ACWR/dor -- é só
        # pra o dado bater com a história).
        na_semana_do_pico = pico_semana_12 and segunda_semana_12 <= d <= fim
        dias.append({
            "data": d,
            "sono_total_seg": 25200 if not na_semana_do_pico else 23400,
            "sono_profundo_seg": 5400,
            "sono_leve_seg": 14400,
            "sono_rem_seg": 5000,
            "sono_desperto_seg": 400,
            "despertares": 2,
            "sono_fc_media": 52.0,
            "sono_estresse_medio": 18.0,
            "sono_score": 78 if not na_semana_do_pico else 66,
            "fc_repouso": 54 if not na_semana_do_pico else 59,
            "fc_repouso_media_7d": 55.0 if not na_semana_do_pico else 58.0,
            "body_battery_ao_acordar": 88 if not na_semana_do_pico else 74,
            "body_battery_mais_recente": 60,
            "body_battery_carregada": 88,
            "body_battery_drenada": 45,
            "estresse_medio_dia": 28.0,
            "passos_totais": 9500,
        })
        d += timedelta(days=1)
    return dias


def _gerar_dor(atividades: list[dict], dor_mais_recente: int | None) -> list[tuple]:
    linhas = []
    for i, dor in DOR_LEVE_NOS_INDICES.items():
        if i < len(atividades):
            a = atividades[i]
            linhas.append((a["activity_id"], a["data"], dor, None, None, "Asfalto", "Asics Gel-Nimbus"))
    if dor_mais_recente is not None:
        ultima = atividades[-1]
        linhas.append((
            ultima["activity_id"], ultima["data"], dor_mais_recente,
            "Canela direita", "Doeu mais no fim do treino, principalmente descendo.",
            "Asfalto", "Asics Gel-Nimbus",
        ))
    return linhas


def _sql_upsert_dor() -> str:
    return (
        "INSERT INTO stg_dor (activity_id, data, dor, localizacao, comentario, superficie, tenis) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (activity_id) DO UPDATE SET dor = excluded.dor, localizacao = excluded.localizacao, "
        "comentario = excluded.comentario, superficie = excluded.superficie, tenis = excluded.tenis"
    )


def main() -> None:
    cenario = os.environ.get("SEED_CENARIO", "ambos")
    if cenario not in CENARIOS:
        raise ValueError(f"SEED_CENARIO desconhecido: {cenario!r} (use um de {list(CENARIOS)})")
    pico, dor_recente = CENARIOS[cenario]

    con = conectar()
    ja_tem_dado = con.execute("SELECT COUNT(*) FROM stg_atividades").fetchone()[0] > 0
    if ja_tem_dado and os.environ.get("SEED_FORCAR") != "true":
        print(
            f"[seed] banco já tem {con.execute('SELECT COUNT(*) FROM stg_atividades').fetchone()[0]} "
            "atividade(s) -- pulando (idempotente). Pra recriar do zero: "
            "`docker compose down -v && docker compose up`, ou SEED_FORCAR=true."
        )
        con.close()
        return

    hoje = hoje_brt()
    segunda_semana_atual = hoje - timedelta(days=hoje.weekday())
    fim_dados = segunda_semana_atual - timedelta(days=1)  # domingo da última semana ISO completa
    inicio_dados = fim_dados - timedelta(weeks=12) + timedelta(days=1)

    print(f"[seed] cenário: {cenario} -- dados de {inicio_dados} a {fim_dados} (12 semanas completas)")

    atividades = _gerar_atividades(fim_dados, pico_semana_12=pico)
    n_ativ = carregar_atividades(con, atividades)
    print(f"[seed] {n_ativ} atividade(s) sintética(s) carregada(s).")

    recuperacao = _gerar_recuperacao(inicio_dados, fim_dados, pico_semana_12=pico)
    n_rec = carregar_recuperacao(con, recuperacao)
    print(f"[seed] {n_rec} dia(s) de recuperação sintético(s) carregado(s).")

    linhas_dor = _gerar_dor(atividades, dor_recente)
    with con.cursor() as cur:
        cur.executemany(_sql_upsert_dor(), linhas_dor)
    print(f"[seed] {len(linhas_dor)} registro(s) de dor carregado(s) (inclui o do cenário '{cenario}').")

    con.close()
    print(
        "\n[seed] pronto. Próximos passos:\n"
        "  docker compose run --rm garmin python -m src.load.planilha_desempenho   # dashboard na planilha\n"
        "  docker compose run --rm garmin python -m src.analyze.analisar_com_ia    # gera o plano da semana\n"
        "Ver README.md / docs/DEMO.md pra mais detalhes."
    )


if __name__ == "__main__":
    main()
