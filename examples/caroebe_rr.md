# Exemplo — Caroebe/RR

Este arquivo documenta a reprodução do recorte de Caroebe, Roraima, a partir do BU oficial de 1º turno de 2026.

## Reprodução

~~~powershell
python scripts/download_bu.py --uf RR
python scripts/process_bu.py --uf RR
~~~

Depois, filtre o resultado por:

SG_UF = RR
NM_MUNICIPIO = CAROEBE

Os valores devem ser lidos do arquivo oficial processado, e não hardcoded neste exemplo.

## Fonte

Tribunal Superior Eleitoral — Resultados 2026 — Boletim de Urna — 1º turno.
