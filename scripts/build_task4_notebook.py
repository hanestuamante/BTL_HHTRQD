"""Chuyển scripts/task4_modeling.py (định dạng cell '# %%') thành notebooks/04_Modeling.ipynb."""
import re
from pathlib import Path

import nbformat

root = Path(__file__).resolve().parent.parent
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
nbformat.write(nb, out)
print("Wrote", out, len(cells), "cells")
