"""Download the Python docs text archive and the PEP sources into corpus/."""

from __future__ import annotations

import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
DOWNLOADS = CORPUS / "_downloads"

DOCS_URL = "https://docs.python.org/3/archives/python-3.15-docs-text.zip"
PEPS_URL = "https://github.com/python/peps/archive/refs/heads/main.zip"
PEPS_COMMIT_URL = "https://api.github.com/repos/python/peps/commits/main"
USER_AGENT = "csci599-assignment2-ingest"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"already downloaded {dest.name}")
        return
    print(f"downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as handle:
        while True:
            block = response.read(1024 * 256)
            if not block:
                break
            handle.write(block)
    print(f"saved {dest.name} ({dest.stat().st_size} bytes)")


def safe_extract(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise RuntimeError(f"unsafe zip path: {info.filename}")
        archive.extractall(dest)


def peps_commit() -> dict:
    request = urllib.request.Request(
        PEPS_COMMIT_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return {
        "sha": payload.get("sha"),
        "committed_at": (payload.get("commit") or {}).get("committer", {}).get("date"),
    }


def main() -> None:
    fetched_at = datetime.now(timezone.utc).isoformat()
    docs_zip = DOWNLOADS / "python-3.15-docs-text.zip"
    peps_zip = DOWNLOADS / "peps-main.zip"
    download(DOCS_URL, docs_zip)
    download(PEPS_URL, peps_zip)
    print("extracting archives")
    safe_extract(docs_zip, CORPUS / "python-docs")
    safe_extract(peps_zip, CORPUS / "peps-src")
    commit = peps_commit()
    manifest = {
        "snapshot_date": fetched_at[:10],
        "fetched_at": fetched_at,
        "python_docs": {
            "version": "3.15",
            "url": DOCS_URL,
            "format": "sphinx-text",
        },
        "peps": {
            "url": PEPS_URL,
            "ref": "main",
            "sha": commit["sha"],
            "committed_at": commit["committed_at"],
        },
    }
    (CORPUS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
