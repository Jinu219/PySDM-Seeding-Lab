from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Iterable
from typing import Any


def safe_plot_stem(title: Any, *, fallback: str = "plot") -> str:
    """Return a filesystem-safe stem while retaining readable Unicode text."""
    stem = re.sub(r"[^\w-]+", "_", str(title), flags=re.UNICODE).strip("_-")
    return (stem or fallback)[:80]


def _write_deterministic_zip_entry(
    archive: zipfile.ZipFile,
    filename: str,
    payload: bytes,
) -> None:
    info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def build_plot_zip_bytes(
    plot_items: Iterable[tuple[Any, bytes]],
) -> bytes:
    """Package rendered PNG payloads and a title manifest into a ZIP archive."""
    rendered_items = list(plot_items)
    manifest_entries = []
    output = io.BytesIO()

    with zipfile.ZipFile(output, mode="w") as archive:
        for index, (title, payload) in enumerate(rendered_items, start=1):
            if not isinstance(payload, (bytes, bytearray, memoryview)):
                raise TypeError("Plot payloads must be bytes-like PNG data.")

            filename = (
                f"{index:02d}_"
                f"{safe_plot_stem(title, fallback=f'plot_{index:02d}')}.png"
            )
            _write_deterministic_zip_entry(archive, filename, bytes(payload))
            manifest_entries.append(
                {
                    "index": index,
                    "title": str(title),
                    "filename": filename,
                }
            )

        manifest = {
            "format": "pysdm-seeding-lab-plot-bundle",
            "version": 1,
            "plot_count": len(manifest_entries),
            "plots": manifest_entries,
        }
        _write_deterministic_zip_entry(
            archive,
            "manifest.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )

    return output.getvalue()
