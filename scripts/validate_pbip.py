"""Kiểm tra PBIP trước khi mở bằng Power BI Desktop.

- JSON hợp lệ và khớp $schema (tải schema công khai của Microsoft).
- Mọi field trong visual tồn tại trong bảng TMDL.
- pageOrder khớp thư mục trang, tên visual không trùng.

Chạy: python scripts/validate_pbip.py
"""
from pathlib import Path
import json
import re
import sys
import urllib.request

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
PROJECT = "BTL_NhiemVu5"
MODEL = DASH / f"{PROJECT}.SemanticModel" / "definition"
REPORT = DASH / f"{PROJECT}.Report" / "definition"

_cache = {}


def schema(url):
    if url not in _cache:
        with urllib.request.urlopen(url, timeout=30) as r:
            _cache[url] = json.load(r)
    return _cache[url]


def check_json(path, use_schema=True):
    data = json.loads(path.read_text(encoding="utf-8"))
    if use_schema and "$schema" in data:
        jsonschema.validate(data, schema(data["$schema"]))
    return data


def model_objects():
    tables, columns, measures = {}, {}, {}
    for f in (MODEL / "tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        name = re.match(r"table\s+(?:'([^']+)'|(\S+))", text)
        if not name:
            continue
        table = name.group(1) or name.group(2)
        tables[table] = f
        columns[table] = set(re.findall(r"^\tcolumn\s+([^\n]+)", text, re.M))
        measures[table] = set(re.findall(r"^\tmeasure\s+'([^']+)'", text, re.M))
    return tables, columns, measures


def walk_refs(node, found):
    if isinstance(node, dict):
        for key in ("Column", "Measure"):
            if key in node and isinstance(node[key], dict):
                ref = node[key]
                entity = ref.get("Expression", {}).get("SourceRef", {}).get("Entity")
                prop = ref.get("Property")
                if entity and prop:
                    found.append((key, entity, prop))
        for value in node.values():
            walk_refs(value, found)
    elif isinstance(node, list):
        for item in node:
            walk_refs(item, found)


def main():
    errors = []
    tables, columns, measures = model_objects()
    if not tables:
        errors.append("Không đọc được bảng nào từ TMDL")

    checked = 0
    for path in REPORT.rglob("*.json"):
        try:
            check_json(path)
            checked += 1
        except jsonschema.ValidationError as exc:
            where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            errors.append(f"{path.relative_to(DASH)}: {where}: {exc.message}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.relative_to(DASH)}: {exc}")

    for path in REPORT.rglob("visual.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        refs = []
        walk_refs(data, refs)
        for kind, entity, prop in refs:
            pool = measures if kind == "Measure" else columns
            if entity not in tables:
                errors.append(f"{path.parent.name}: bảng '{entity}' không tồn tại")
            elif prop not in pool.get(entity, set()):
                errors.append(f"{path.parent.name}: {kind} '{entity}.{prop}' không tồn tại")

    pages = json.loads((REPORT / "pages" / "pages.json").read_text(encoding="utf-8"))
    for name in pages["pageOrder"]:
        if not (REPORT / "pages" / name / "page.json").exists():
            errors.append(f"Thiếu page.json cho trang '{name}'")
    if pages["activePageName"] not in pages["pageOrder"]:
        errors.append("activePageName không nằm trong pageOrder")

    names = [json.loads(p.read_text(encoding="utf-8"))["name"]
             for p in REPORT.rglob("visual.json")]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        errors.append(f"Tên visual trùng: {sorted(dupes)}")

    print(f"Đã kiểm tra {checked} file JSON, {len(names)} visual, {len(tables)} bảng.")
    if errors:
        print("\nLỖI:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("PBIP hợp lệ.")


if __name__ == "__main__":
    main()
