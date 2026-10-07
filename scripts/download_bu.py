#!/usr/bin/env python3
"""Download official 1st-round BU ZIPs from the TSE CKAN catalog."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

API_URL = "https://dadosabertos.tse.jus.br/api/3/action/package_show"
DATASET_ID = "resultados-2026-boletim-de-urna"
UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
RAW_DIR = Path("data/raw")
TIMEOUT = 120


def get_catalog() -> dict:
    response = requests.get(
        API_URL,
        params={"id": DATASET_ID},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError("A API CKAN do TSE retornou success=false.")
    return payload["result"]


def find_resource(catalog: dict, uf: str) -> tuple[str, str]:
    prefix = f"{uf} - Boletim de Urna - Primeiro turno"
    matches = [
        resource
        for resource in catalog["resources"]
        if resource.get("name", "").startswith(prefix)
        and resource.get("url", "").lower().endswith(".zip")
    ]
    if not matches:
        raise RuntimeError(
            f"Recurso ZIP de 1º turno não encontrado para {uf}."
        )
    resource = matches[0]
    return resource["url"], resource.get("name", resource["url"])


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", "0"))
        with destination.open("wb") as output:
            with tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc=destination.name,
            ) as progress:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        output.write(chunk)
                        progress.update(len(chunk))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa BUs oficiais do TSE para o 1º turno de 2026."
    )
    parser.add_argument("--uf", default="ALL", help="UF ou ALL.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    selected = (
        UFS if args.uf.upper() == "ALL"
        else [args.uf.upper()]
    )
    invalid = [uf for uf in selected if uf not in UFS]
    if invalid:
        raise SystemExit(f"UF inválida: {', '.join(invalid)}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    catalog = get_catalog()

    for uf in selected:
        url, resource_name = find_resource(catalog, uf)
        filename = Path(urlparse(url).path).name

        if not re.fullmatch(
            r"bweb_1t_[A-Z]{2}_.*\.zip",
            filename,
        ):
            raise RuntimeError(
                f"Nome inesperado do recurso {uf}: {filename}"
            )

        destination = RAW_DIR / uf / filename
        if destination.exists() and not args.force:
            logging.info(
                "%s: arquivo já existe: %s",
                uf,
                destination,
            )
            continue

        logging.info("%s: %s", uf, resource_name)
        download(url, destination)
        logging.info("%s: download concluído", uf)


if __name__ == "__main__":
    main()
