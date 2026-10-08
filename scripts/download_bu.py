#!/usr/bin/env python3
"""Download official 1st-round BU ZIPs from the TSE CDN."""

from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

CDN_BASE_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/eleicoes/"
    "eleicoes2026/buweb"
)
BU_SUFFIX = "051020261403"
UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
RAW_DIR = Path("data/raw")
TIMEOUT = 120
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://dadosabertos.tse.jus.br/",
}


def resource_url(uf: str) -> str:
    return f"{CDN_BASE_URL}/bweb_1t_{uf}_{BU_SUFFIX}.zip"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    last_error: requests.HTTPError | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with requests.get(
                url,
                headers=DOWNLOAD_HEADERS,
                stream=True,
                timeout=TIMEOUT,
            ) as response:
                if response.status_code == 403 and attempt < DOWNLOAD_ATTEMPTS:
                    logging.warning(
                        "Download blocked with HTTP 403 (attempt %s/%s); "
                        "retrying with backoff",
                        attempt,
                        DOWNLOAD_ATTEMPTS,
                    )
                    time.sleep(2 ** attempt)
                    continue

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
                return
        except requests.HTTPError as exc:
            last_error = exc
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            logging.warning(
                "HTTP error during download (attempt %s/%s): %s; retrying",
                attempt,
                DOWNLOAD_ATTEMPTS,
                exc,
            )
            time.sleep(2 ** attempt)

    if last_error is not None:
        raise last_error


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

    for uf in selected:
        url = resource_url(uf)
        filename = Path(urlparse(url).path).name

        if not re.fullmatch(
            r"bweb_1t_[A-Z]{2}_[0-9]{12}\.zip",
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

        logging.info("%s: %s", uf, url)
        download(url, destination)
        logging.info("%s: download concluído", uf)


if __name__ == "__main__":
    main()
