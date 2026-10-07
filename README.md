# TSE BU Presidencial 2026

Pipeline reproduzível para consolidar, por seção eleitoral, os votos para Presidente no 1º turno das Eleições 2026 a partir dos Boletins de Urna oficiais do Tribunal Superior Eleitoral (TSE).

## Objetivo

Gerar uma tabela única com uma linha por seção encontrada nos BUs oficiais das 27 UFs brasileiras, contendo:

- SG_UF
- CD_MUNICIPIO
- NM_MUNICIPIO
- NR_ZONA
- NR_SECAO
- NR_LOCAL_VOTACAO
- NR_URNA_EFETIVADA
- QT_APTOS
- QT_COMPARECIMENTO
- QT_ABSTENCOES
- DT_ABERTURA
- DT_ENCERRAMENTO
- DT_EMISSAO_BU
- DT_BU_RECEBIDO
- VOTOS_FLAVIO_BOLSONARO
- VOTOS_LULA
- VOTOS_BRANCO_PRES
- VOTOS_NULO_PRES
- TOTAL_VOTOS_PRES

O TSE disponibiliza o conjunto "Resultados - 2026 - Boletim de Urna" por UF e alerta que os arquivos possuem grande volume de linhas. Este projeto usa processamento incremental e armazenamento temporário em SQLite para evitar carregar uma UF inteira na memória.

## Fonte oficial

Portal de Dados Abertos do TSE:
https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna

Os recursos de 1º turno são publicados por UF. O recurso ZZ (exterior) não é incluído na tabela das 27 UFs brasileiras.

## Regras de negócio

- somente 1º turno;
- somente cargo Presidente (CD_CARGO_PERGUNTA = 1);
- candidato 22: Flávio Bolsonaro;
- candidato 13: Lula;
- código 95: voto em branco;
- código 96: voto nulo;
- TOTAL_VOTOS_PRES é a soma dos quatro componentes acima;
- uma linha final representa uma seção efetivamente encontrada no BU oficial;
- nenhuma seção ausente é criada artificialmente com zeros.

A identificação de Flávio Bolsonaro (22) e Lula (13) é consistente com a relação oficial de candidaturas do TSE para 2026.

## Requisitos

- Python 3.10+
- pandas
- requests
- tqdm
- tabulate

## Instalação

~~~powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
~~~

## Uso

Baixar uma UF:

~~~powershell
python scripts/download_bu.py --uf RR
~~~

Processar uma UF:

~~~powershell
python scripts/process_bu.py --uf RR
~~~

Gerar a tabela consolidada:

~~~powershell
python scripts/generate_table.py --uf RR
~~~

Executar tudo para uma UF:

~~~powershell
python scripts/process_bu.py --uf RR --download
~~~

Executar todas as 27 UFs:

~~~powershell
python scripts/process_bu.py --uf ALL --download
python scripts/generate_table.py --uf ALL
~~~

## Saídas

~~~text
data/
├── raw/
│   └── <UF>/
│       └── bweb_1t_<UF>_*.zip
└── processed/
    ├── votacao_presidencial_<UF>_2026.csv
    ├── votacao_presidencial_<UF>_2026.md
    └── votacao_presidencial_por_secao_2026.csv
~~~

Os ZIPs originais não são versionados no Git. Eles podem ser recriados pelo downloader a partir da fonte oficial.

## Processamento incremental

O pipeline consulta o catálogo CKAN do TSE, localiza o recurso CSV oficial da UF, baixa o ZIP em streaming, lê cada CSV em chunks, filtra Presidente, agrega os votos por seção, grava o estado intermediário em SQLite e exporta o resultado final.

## Validações

O gerador verifica:

- presença de todas as colunas obrigatórias;
- ausência de duplicidade na chave de seção;
- valores de voto não negativos;
- igualdade de TOTAL_VOTOS_PRES à soma dos quatro componentes;
- escopo exclusivo das 27 UFs.

## Exemplo

Veja examples/caroebe_rr.md.

## Licença e atribuição

Os dados são provenientes do TSE. Consulte a licença e os termos do Portal de Dados Abertos para as condições de uso.

Este repositório é uma transformação técnica dos dados oficiais e não é uma publicação oficial do TSE.
