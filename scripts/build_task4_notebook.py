"""Chuyển scripts/task4_modeling.py (định dạng cell '# %%') thành notebooks/04_Modeling.ipynb và THỰC THI notebook.

    python scripts/build_task4_notebook.py              # tạo + chạy (~30 phút, ghi đè đầu ra cũ)
    python scripts/build_task4_notebook.py --no-execute  # chỉ tạo cell, không chạy

Build mà không execute sẽ xóa đầu ra đã lưu, nên mặc định luôn execute (feedback mục "Notebook NV4").
"""
import argparse
import re
import sys
from pathlib import Path

import nbformat

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--no-execute", action="store_true")
ap.add_argument("--timeout", type=int, default=7200)
args = ap.parse_args()

src = (root / "scripts" / "task4_modeling.py").read_text(encoding="utf-8")
cells = []
for block in re.split(r"^(?=# %%)", src, flags=re.M):
    if not block.strip():
        continue
    header, _, body = block.partition("\n")
    if header.startswith("# %% [markdown]"):
        md = "\n".join(line[2:] if line.startswith("# ") else line.lstrip("#") for line in body.strip().splitlines())
        cells.append(nbformat.v4.new_markdown_cell(md))
    else:
        cells.append(nbformat.v4.new_code_cell(body.strip()))
nb = nbformat.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
out = root / "notebooks" / "04_Modeling.ipynb"
if not args.no_execute:
    from nbclient import NotebookClient
    print(f"Executing {len(cells)} cells (cwd = notebooks/) ...", flush=True)
    NotebookClient(nb, timeout=args.timeout, kernel_name="python3",
                   resources={"metadata": {"path": str(root / "notebooks")}}).execute()
    errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"]
    if errors:
        sys.exit(f"Notebook có {len(errors)} lỗi")
nbformat.write(nb, out)
n_code = sum(c.cell_type == "code" for c in cells)
print("Wrote", out, f"{len(cells)} cells ({n_code} code)", "executed" if not args.no_execute else "NOT executed")
