from __future__ import annotations

"""Small, credential-safe client for the ARM Live Data Web Service."""

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


ARM_LIVE_QUERY_ENDPOINT = "https://adc.arm.gov/armlive/query"
ARM_LIVE_DOWNLOAD_ENDPOINT = "https://adc.arm.gov/armlive/saveData"
_SAFE_DATASTREAM = re.compile(r"^[A-Za-z0-9_.-]+$")
_SAFE_FILE_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.(?:cdf|nc)$", re.IGNORECASE)


def _validate_credentials(user_id: str, access_token: str) -> tuple[str, str]:
    user = str(user_id).strip()
    token = str(access_token).strip()
    if not user or not token:
        raise ValueError("ARM user ID and access token must be non-blank.")
    if any(character.isspace() for character in user + token):
        raise ValueError("ARM credentials cannot contain whitespace.")
    return user, token


def _validate_datastream(datastream: str) -> str:
    value = str(datastream).strip()
    if not value or not _SAFE_DATASTREAM.fullmatch(value):
        raise ValueError("ARM datastream contains unsupported characters.")
    return value


def _validate_date(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if not normalized or any(character.isspace() for character in normalized):
        raise ValueError(f"ARM {field} must be a non-blank date without spaces.")
    if not re.fullmatch(r"[0-9T:./+-]+Z?", normalized):
        raise ValueError(f"ARM {field} contains unsupported characters.")
    return normalized


def build_arm_query_url(
    *,
    user_id: str,
    access_token: str,
    datastream: str,
    start: str,
    end: str,
) -> str:
    user, token = _validate_credentials(user_id, access_token)
    parameters = {
        "user": f"{user}:{token}",
        "ds": _validate_datastream(datastream),
        "start": _validate_date(start, field="start"),
        "end": _validate_date(end, field="end"),
        "wt": "json",
    }
    return ARM_LIVE_QUERY_ENDPOINT + "?" + urllib.parse.urlencode(parameters)


def build_arm_download_url(
    *,
    user_id: str,
    access_token: str,
    file_name: str,
) -> str:
    user, token = _validate_credentials(user_id, access_token)
    name = str(file_name).strip()
    if not _SAFE_FILE_NAME.fullmatch(name):
        raise ValueError("ARM file name must be a basename ending in .cdf or .nc.")
    parameters = {"user": f"{user}:{token}", "file": name}
    return ARM_LIVE_DOWNLOAD_ENDPOINT + "?" + urllib.parse.urlencode(parameters)


def redact_arm_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url))
    parameters = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [
        (key, "REDACTED" if key == "user" else value)
        for key, value in parameters
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), "")
    )


def _collect_file_names(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, str):
        parsed = urllib.parse.urlsplit(payload)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        candidate = Path(query.get("file", parsed.path or payload)).name
        if _SAFE_FILE_NAME.fullmatch(candidate):
            found.append(candidate)
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_collect_file_names(value))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in {
                "files",
                "file",
                "filename",
                "name",
                "url",
                "data",
                "results",
            }:
                found.extend(_collect_file_names(value))
    return sorted(set(found))


def query_arm_file_names(
    *,
    user_id: str,
    access_token: str,
    datastream: str,
    start: str,
    end: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[str]:
    url = build_arm_query_url(
        user_id=user_id,
        access_token=access_token,
        datastream=datastream,
        start=start,
        end=end,
    )
    try:
        with opener(url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "ARM Live query failed for " + redact_arm_url(url)
        ) from None
    file_names = _collect_file_names(payload)
    if not file_names:
        raise RuntimeError(
            "ARM Live returned no NetCDF file names for the requested datastream "
            "and interval. The data may require a regular archive order."
        )
    return file_names


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_arm_files(
    file_names: list[str],
    *,
    user_id: str,
    access_token: str,
    output_dir: str | Path,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for file_name in file_names:
        url = build_arm_download_url(
            user_id=user_id,
            access_token=access_token,
            file_name=file_name,
        )
        output_path = destination / file_name
        partial_path = output_path.with_name(output_path.name + ".part")
        if output_path.exists() or partial_path.exists():
            raise FileExistsError(f"ARM destination already exists: {output_path}")
        try:
            with opener(url, timeout=120) as response, partial_path.open("xb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            os.replace(partial_path, output_path)
        except Exception as exc:
            partial_path.unlink(missing_ok=True)
            raise RuntimeError(
                "ARM Live download failed for " + redact_arm_url(url)
            ) from None
        records.append(
            {
                "file_name": file_name,
                "size_bytes": output_path.stat().st_size,
                "sha256": _sha256(output_path),
            }
        )
    return records
