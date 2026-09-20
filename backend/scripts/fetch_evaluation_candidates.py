#!/usr/bin/env python3
"""Download explicitly licensed Wikimedia Commons evaluation photos.

This helper does not decide ground truth and does not manufacture difficult
conditions. The evaluator dataset should primarily use photographs collected by
the team or other real source material that has an appropriate redistribution
license. Every image must still be visually inspected and hand-verified before it
is included in the measurement set.

The script downloads the ORIGINAL image returned by Commons, not a thumbnail.
It records author/licence/checksum metadata after each successful download so a
mid-run failure does not lose progress.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = ROOT / "docs/evaluation/sources.json"
DEFAULT_OUTPUT = ROOT / "docs/evaluation/images"
USER_AGENT = "SIH26034-evaluation-dataset/1.1"


def _title_from_url(page_url: str) -> str:
    path = urllib.parse.urlparse(page_url).path
    marker = "/File:"
    if marker not in path:
        raise ValueError(f"not a Wikimedia Commons file URL: {page_url}")
    return urllib.parse.unquote(path.split(marker, 1)[1])


def _api_file_info(title: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime|sha1",
            "titles": f"File:{title}",
        }
    )
    req = urllib.request.Request(
        f"https://commons.wikimedia.org/w/api.php?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    page = next(iter(payload["query"]["pages"].values()))
    info = page.get("imageinfo")
    if not info:
        raise RuntimeError(f"Commons returned no image information for {title}")
    return info[0]


def _meta(ext: dict, key: str) -> str | None:
    value = ext.get(key, {}).get("value")
    if value is None:
        return None
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _default_filename(source: dict, original_url: str) -> str:
    explicit = source.get("filename")
    if explicit:
        return str(explicit)
    title = Path(urllib.parse.unquote(urllib.parse.urlparse(original_url).path)).name
    title = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")
    return f"{source['id']}_{title or 'image.jpg'}"


def _save_progress(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--id", dest="source_id", action="append", help="download only this source id; repeatable")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.sources.read_text(encoding="utf-8"))
    selected = {
        str(value): True for value in args.source_id
    } if args.source_id else None
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for source in data["sources"]:
        if selected is not None and str(source["id"]) not in selected:
            continue
        try:
            title = _title_from_url(source["page_url"])
            info = _api_file_info(title)
            url = info["url"]
            filename = _default_filename(source, url)
            destination = args.output_dir / filename

            source["downloaded_filename"] = filename
            source["resolved_original_url"] = url
            source["sha1"] = info.get("sha1")
            source["author"] = _meta(info.get("extmetadata", {}), "Artist")
            source["license"] = _meta(info.get("extmetadata", {}), "LicenseShortName")
            source["license_url"] = _meta(info.get("extmetadata", {}), "LicenseUrl")
            source["credit"] = _meta(info.get("extmetadata", {}), "Credit")
            source["usage_terms"] = _meta(info.get("extmetadata", {}), "UsageTerms")

            if destination.exists() and not args.overwrite:
                source["download_status"] = "existing"
                _save_progress(args.sources, data)
                print(f"SKIP {filename}")
                continue

            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as response:
                destination.write_bytes(response.read())

            source["download_status"] = "downloaded"
            _save_progress(args.sources, data)
            print(f"GET  {filename}")
        except Exception as exc:
            source["download_status"] = "error"
            source["download_error"] = f"{type(exc).__name__}: {exc}"
            _save_progress(args.sources, data)
            print(f"FAIL {source['id']}: {source['download_error']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
