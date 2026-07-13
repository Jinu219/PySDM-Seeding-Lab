from __future__ import annotations

from pathlib import Path
import re

DASHBOARD_PATH = Path("analysis/dashboard.py")
SAFE_BLOCK = 'def safe_read_csv(path: Path) -> pd.DataFrame:\n    """\n    Read a CSV without crashing the dashboard.\n\n    Returns an empty DataFrame when:\n    - file does not exist\n    - file exists but is zero-byte / headerless\n    - pandas raises EmptyDataError\n    """\n    path = Path(path)\n\n    if not path.exists():\n        return pd.DataFrame()\n\n    try:\n        if path.stat().st_size == 0:\n            return pd.DataFrame()\n    except OSError:\n        return pd.DataFrame()\n\n    try:\n        return pd.read_csv(path)\n    except pd.errors.EmptyDataError:\n        return pd.DataFrame()\n    except FileNotFoundError:\n        return pd.DataFrame()\n\n\ndef flatten_summary'

def main() -> None:
    text = DASHBOARD_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r"def safe_read_csv\(path: Path\) -> pd\.DataFrame:\n[\s\S]+?\n\n\ndef flatten_summary",
        re.MULTILINE,
    )
    new_text, n = pattern.subn(SAFE_BLOCK, text)
    if n == 0:
        raise RuntimeError("Could not find safe_read_csv block in analysis/dashboard.py")
    DASHBOARD_PATH.write_text(new_text, encoding="utf-8")
    print("Fixed analysis/dashboard.py safe_read_csv recursion.")

if __name__ == "__main__":
    main()
