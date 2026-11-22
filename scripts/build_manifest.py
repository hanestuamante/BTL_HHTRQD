"""Tạo lại / kiểm tra metadata/delivery_manifest.json (SHA256 của mọi file bàn giao).

    python scripts/build_manifest.py           # ghi manifest
    python scripts/build_manifest.py --check   # so file hiện tại với manifest, báo file lệch/thiếu
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "metadata" / "delivery_manifest.json"
INCLUDE_DIRS = ["bds_valuation", "scripts", "tests", "data", "dictionaries", "metadata", "docs", "notebooks",
                "outputs", "models", "reports", "dashboard", "slides"]
INCLUDE_FILES = ["README.md", "Huong_dan.txt", "requirements.txt", "requirements_task4.txt", "pytest.ini"]
SKIP_PARTS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache"}


def files():
    out = [ROOT / f for f in INCLUDE_FILES if (ROOT / f).exists()]
    for d in INCLUDE_DIRS:
        out += [p for p in (ROOT / d).rglob("*") if p.is_file() and not SKIP_PARTS & set(p.parts)
                and p.name != ".DS_Store" and p != MANIFEST]
    return sorted(out)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    current = {p.relative_to(ROOT).as_posix(): sha(p) for p in files()}
    if a.check:
        saved = json.loads(MANIFEST.read_text(encoding="utf-8"))
        bad = [k for k in saved if current.get(k) != saved[k]]
        new = [k for k in current if k not in saved]
        print(f"{len(saved) - len(bad)}/{len(saved)} checksum khớp; lệch/thiếu: {bad or 'không'}; file mới chưa có: {new or 'không'}")
        return 1 if bad else 0
    MANIFEST.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} ({len(current)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
