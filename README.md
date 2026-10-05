# Garmin_data_colector — demo pública

Demo pública de um pipeline pessoal (privado) que coleta dados do Garmin
Forerunner 165 e gera, toda semana, recomendações de treino via IA que
marquem evolução — com cuidado pra não repetir o padrão de sobrecarga que
já causou canelite (síndrome do estresse tibial medial) uma vez. Contexto
de negócio completo, metodologia CRISP-DM, em
[`docs/ENTENDIMENTO_DO_NEGOCIO.md`](docs/ENTENDIMENTO_DO_NEGOCIO.md) (ou
[`.pdf`](docs/ENTENDIMENTO_DO_NEGOCIO.pdf)).

Este repositório existe pra permitir testar o sistema completo sem
precisar de conta na Garmin, sem acesso a dado de saúde real de ninguém e
sem depender de infraestrutura paga. O código do pipeline em si (`src/`)
é o mesmo do projeto original — schema do banco, os dois guardrails
determinísticos (ACWR e dor recente), a regra de composição de treino
(polarização 80/20), a revisão de coerência por um segundo LLM
independente. O que muda é só a borda: de onde vem o dado e qual LLM gera
o plano.

Alguns comentários no código citam `CASE_DO_PROJETO_1.md` (seção X) —
é a documentação completa do projeto original, privada, e não faz parte
deste repositório. Ficam como registro de que aquela decisão foi
pesquisada e documentada, mesmo sem o link resolver aqui.

## O que é real e o que é mockado nesta demo

| Peça | Projeto original | Nesta demo |
|---|---|---|
| Dado de treino/sono | Garmin Connect (conta real) | Sintético, gerado por [`scripts/seed_demo.py`](scripts/seed_demo.py) -- 12 semanas, sem nenhum dado de saúde real |
| Banco | Neon (Postgres gerenciado, na nuvem) | Postgres local, no próprio `docker-compose.yml` |
| Envio ao relógio (Fase 12) | API da Garmin, relógio real | Mockado -- só imprime o que seria enviado (`GARMIN_MOCK=true`, padrão) |
| Planilha (Google Sheets) | Real, planilha pessoal | Real, com uma planilha e uma conta de serviço de teste (descartável, criada só pra esta demo) |
| E-mail (Gmail SMTP) | Real, e-mail pessoal | Real, com uma conta de teste (descartável, criada só pra esta demo) |
| Plano de treino (LLM) | Gemini (Google AI Studio) | Configurável: `mock` (padrão, instantâneo), `ollama` (modelo local, sem custo, gera treino de verdade) ou `gemini` (com sua própria chave) |

## Testar em poucos minutos

Pré-requisito: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up
```

Isso sobe o Postgres local e o Ollama, builda a imagem da app e roda o
seed automaticamente (idempotente -- rodar de novo não duplica nada). No
final, o terminal mostra os próximos comandos. Com `LLM_PROVEDOR=mock`
(padrão do `.env.example`), tudo funciona sem baixar nada:

```bash
docker compose run --rm garmin python -m src.load.planilha_desempenho   # dashboard na planilha
docker compose run --rm garmin python -m src.analyze.analisar_com_ia    # gera o plano da semana
```

O plano gerado aparece no terminal, na aba "Plano da Semana" da planilha
(ver credenciais abaixo) e por e-mail. O guardrail de ACWR e o de dor
recente disparam nesse primeiro teste, porque o cenário padrão do seed
(`SEED_CENARIO=ambos`) foi construído pra isso -- ver seção abaixo.

## Gerando o treino de verdade (Ollama, local)

Por padrão a demo usa `LLM_PROVEDOR=mock` -- planos pré-gravados que
reagem aos guardrails, sem chamar LLM nenhum (ver
[`src/llm/mock.py`](src/llm/mock.py)). Pra gerar o plano de verdade, com
um modelo rodando local em Docker, sem conta e sem custo:

```bash
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

(uns 2-5GB, primeira vez só). Depois, no `.env`:

```
LLM_PROVEDOR=ollama
```

E rode `docker compose run --rm garmin python -m src.analyze.analisar_com_ia`
de novo. Sem GPU (padrão no Docker Desktop Windows/Mac) isso roda em CPU
-- pode levar alguns minutos por tentativa (geração + revisão de
coerência, até 3 tentativas). Também é menos confiável que o Gemini real,
principalmente como revisor: um modelo pequeno tende a aprovar plano que
um modelo maior reprovaria. Se `LLM_PROVEDOR=ollama` falhar ou travar,
volte pra `mock` no `.env` pra continuar testando o resto do pipeline.

Com sua própria chave do Gemini (comportamento real do projeto original):
`LLM_PROVEDOR=gemini` e `GEMINI_API_KEY` no `.env` (gratuita em
aistudio.google.com/apikey).

## Os cenários do seed (`SEED_CENARIO` no `.env`)

O seed ([`scripts/seed_demo.py`](scripts/seed_demo.py)) gera sempre as
mesmas 11 primeiras semanas (progressão gradual de base, sem nenhum
guardrail disparando) -- só a 12ª semana (mais recente) muda:

- **`ambos`** (padrão): pico de volume (ACWR ~1.51, acima do limiar de
  risco alto de 1.5) **e** dor registrada no treino mais recente (nível
  3) -- os dois guardrails disparando juntos.
- **`acwr`**: só o pico de volume.
- **`dor`**: só a dor recente, volume normal.
- **`normal`**: nenhum guardrail dispara -- semana de progressão comum.

Os quatro foram validados rodando o seed contra um Postgres real e
consultando `vw_resumo_semanal`/`vw_sessoes_ia` diretamente, não só
calculados de cabeça. Pra trocar de cenário: mude `SEED_CENARIO` no
`.env`, `docker compose down -v` (apaga o volume do banco) e
`docker compose up` de novo.

## Credenciais da planilha e do e-mail (conta de teste)

Google Sheets e Gmail continuam reais nesta demo -- não fazia sentido
mockar a saída principal do pipeline. As credenciais abaixo são de uma
conta descartável, criada só pra esta demo (não é a conta pessoal de
ninguém):

- **Planilha:** [abrir no Google Sheets](https://docs.google.com/spreadsheets/d/10dS1PLu66De5rJxoi7SdHQD4nEcRJAc49ybxa2mBrmI/edit).
  A chave da conta de serviço (projeto `garmin-demo`) já está neste
  repositório, em [`.google_sheets_credentials.json`](.google_sheets_credentials.json)
  -- é onde o `.env.example` já aponta, não precisa mexer.
- **E-mail:** conta Gmail de teste `t52650125@gmail.com`, com uma senha de
  app (não é a senha da conta).

Falta só colar estas três linhas no seu `.env` local (depois de
`cp .env.example .env`):

```
GOOGLE_SHEET_ID=10dS1PLu66De5rJxoi7SdHQD4nEcRJAc49ybxa2mBrmI
EMAIL_REMETENTE=t52650125@gmail.com
EMAIL_SENHA_APP=hmcoutuwtbxbpyjk
```

O plano da semana chega por e-mail na própria conta de teste (sem
`EMAIL_DESTINATARIO`, o destinatário é o remetente); pra receber na sua
caixa, defina `EMAIL_DESTINATARIO=seu@email.com` no `.env`.

**Não precisa criar conta em lugar nenhum** pra rodar esta demo. Como
estas credenciais são públicas, qualquer pessoa pode editar essa planilha
ou usar essa conta pra enviar e-mail: tratam-se de recursos descartáveis,
sem nenhum dado real, e podem ser revogados a qualquer momento. Se algo
parar de funcionar (planilha apagada, senha de app revogada), use as suas
próprias credenciais: Google Cloud -> ativar a Sheets API -> criar uma
conta de serviço e baixar a chave JSON (substitui
`.google_sheets_credentials.json`) -> compartilhar a sua planilha com o
`client_email` da conta; e, no Gmail, gerar uma senha de app em
myaccount.google.com/apppasswords.

## Estrutura do projeto

```
├── docker-compose.yml          # Postgres local + Ollama + app (substitui Neon/Gemini do original)
├── scripts/seed_demo.py        # gera 12 semanas de dado sintético (substitui extract/garmin.py)
├── src/
│   ├── db.py                   # conexão Postgres + aplica schema.sql (sem mudança)
│   ├── planilha.py              # Google Sheets (sem mudança)
│   ├── email_util.py           # Gmail SMTP (sem mudança)
│   ├── extract/garmin.py       # API real da Garmin -- presente mas não chamado nesta demo (GARMIN_MOCK=true)
│   ├── llm/                    # NOVO nesta demo: mock/ollama/gemini atrás da mesma interface
│   ├── load/
│   │   ├── schema.sql           # mesmo schema do projeto original
│   │   ├── load_atividades.py / load_recuperacao.py  # sem mudança (recebem dado do seed em vez do Garmin)
│   │   ├── load_dor.py / planilha_desempenho.py       # sem mudança
│   └── analyze/analisar_com_ia.py  # adaptado: usa src/llm + mock do envio ao relógio (Fase 12)
└── docs/
    └── ENTENDIMENTO_DO_NEGOCIO.md/.pdf  # entendimento de negócio (CRISP-DM) do projeto original
```

## Limitações conhecidas

- O provedor `mock` não demonstra a revisão de coerência *reprovando* um
  plano -- isso só acontece com um LLM que de fato raciocina sobre o
  conteúdo (`ollama`/`gemini`).
- `ollama` com modelo pequeno pode falhar em produzir JSON válido contra
  o schema, ou levar vários minutos numa máquina sem GPU.
- A planilha e o e-mail usam uma conta de teste real, compartilhada por
  quem for rodar esta demo -- não é uma simulação isolada por pessoa.

## Solução de problemas

- **`docker compose up` trava/erro de porta 5432 ou 11434 ocupada**:
  outro processo (Postgres/Ollama local) já usa essas portas -- pare o
  outro processo, ou remova o `ports:` correspondente no
  `docker-compose.yml` (não é necessário pra app funcionar, é só pra
  inspecionar de fora).
- **`ollama` muito lento ou travando**: normal em CPU. Volte pra
  `LLM_PROVEDOR=mock` no `.env` pra continuar testando.
- **Quero recomeçar do zero**: `docker compose down -v` remove os
  volumes (banco e modelo do Ollama baixado) -- `docker compose up`
  reconstrói tudo.
