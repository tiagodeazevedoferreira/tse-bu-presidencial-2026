# Exemplo — Caroebe/RR

Este arquivo documenta a reprodução do recorte de Caroebe, Roraima, a partir do BU oficial de 1º turno de 2026.

## Identificação

- UF: RR
- Código do município: 3000
- Município: CAROEBE
- Zona: 4
- Seções no resultado consolidado: 30

## Totais reproduzidos

| Campo | Total |
|---|---:|
| QT_APTOS | 7.649 |
| QT_COMPARECIMENTO | 6.612 |
| QT_ABSTENCOES | 1.037 |
| VOTOS_FLAVIO_BOLSONARO | 4.989 |
| VOTOS_LULA | 1.201 |
| VOTOS_BRANCO_PRES | 46 |
| VOTOS_NULO_PRES | 93 |
| TOTAL_VOTOS_PRES | 6.329 |

A reconciliação eleitoral é preservada: 7.649 = 6.612 + 1.037 e 6.329 = 4.989 + 1.201 + 46 + 93.

## Reprodução

~~~powershell
python scripts/download_bu.py --uf RR
python scripts/process_bu.py --uf RR
~~~

Depois, filtre o resultado por:

~~~text
SG_UF = RR
CD_MUNICIPIO = 3000
NM_MUNICIPIO = CAROEBE
~~~

Os valores deste exemplo foram conferidos contra o artefato nacional validado do workflow 27-UF de 07/10/2026; não são valores hardcoded no pipeline.

## Fonte

Tribunal Superior Eleitoral — Resultados 2026 — Boletim de Urna — 1º turno.
