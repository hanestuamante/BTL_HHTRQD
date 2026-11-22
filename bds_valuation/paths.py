"""Tìm thư mục gốc project, không phụ thuộc thư mục đang chạy (F11).

Thứ tự ưu tiên:
1. Biến môi trường ``BDS_PROJECT_ROOT`` (dùng khi chạy từ một thư mục bất kỳ).
2. Đi ngược lên từ ``start`` (script truyền ``Path(__file__)``; notebook truyền ``Path.cwd()``)
   cho tới thư mục chứa cả ``bds_valuation/`` và ``data/processed/``.
Không tìm thấy thì báo lỗi rõ ràng thay vì đọc nhầm dữ liệu.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "BDS_PROJECT_ROOT"
MARKERS = ("bds_valuation", "data/processed")


def is_project_root(path: Path) -> bool:
    return all((path / m).is_dir() for m in MARKERS)


def find_project_root(start: str | Path | None = None) -> Path:
    env = os.environ.get(ENV_VAR)
    if env:
        root = Path(env).expanduser().resolve()
        if not is_project_root(root):
            raise FileNotFoundError(f"{ENV_VAR}={env} không phải thư mục gốc project (thiếu {MARKERS}).")
        return root
    start = Path(start or Path.cwd()).expanduser().resolve()
    if start.is_file():
        start = start.parent
    for cand in (start, *start.parents):
        if is_project_root(cand):
            return cand
    raise FileNotFoundError(
        f"Không tìm thấy thư mục gốc project từ {start}. Chạy trong thư mục project hoặc đặt "
        f"biến môi trường {ENV_VAR}=<đường dẫn tới thư mục chứa bds_valuation/ và data/>."
    )


def project_paths(root: Path) -> dict[str, Path]:
    paths = {
        "root": root,
        "data": root / "data" / "processed",
        "tables": root / "outputs" / "task4" / "tables",
        "figures": root / "outputs" / "task4" / "figures",
        "models": root / "models",
        "metadata": root / "metadata",
    }
    for key in ("tables", "figures", "models"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths
