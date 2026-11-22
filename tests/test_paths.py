"""F11: tìm thư mục gốc từ root, scripts, notebooks, đường dẫn tuyệt đối từ ngoài project."""
import os
import subprocess
import sys

import pytest

from bds_valuation.paths import ENV_VAR, find_project_root


@pytest.mark.parametrize("sub", ["", "scripts", "notebooks", "bds_valuation"])
def test_find_root_from_subdirs(root, sub, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert find_project_root(root / sub) == root


def test_find_root_from_file(root, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert find_project_root(root / "scripts" / "task4_modeling.py") == root


def test_outside_project_needs_env(root, tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(FileNotFoundError, match=ENV_VAR):
        find_project_root(tmp_path)
    monkeypatch.setenv(ENV_VAR, str(root))
    assert find_project_root(tmp_path) == root
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    with pytest.raises(FileNotFoundError):
        find_project_root()


def test_import_does_not_train_and_cli_runs_from_outside(root, tmp_path):
    code = ("import time,sys; sys.path.insert(0, %r); t=time.time(); "
            "import bds_valuation.predict, bds_valuation.models, bds_valuation.evaluation, bds_valuation.selection; "
            "print(time.time()-t)") % str(root)
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert float(out.stdout.strip()) < 30
    if (root / "models" / "model.pkl").exists():
        src = tmp_path / "in.csv"
        import pandas as pd
        pd.read_csv(root / "data/raw/kc_house_data.csv", nrows=20).to_csv(src, index=False)
        env = {**os.environ, "PYTHONPATH": str(root)}
        subprocess.run([sys.executable, "-m", "bds_valuation.predict", str(src), str(tmp_path / "out.csv")],
                       cwd=tmp_path, env=env, check=True, capture_output=True)
        assert (tmp_path / "out.csv").exists()
