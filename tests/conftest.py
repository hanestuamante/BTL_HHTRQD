import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def king_clean(root):
    return pd.read_csv(root / "data" / "processed" / "king_county_clean.csv", dtype={"id": "string", "zipcode": "string"})


@pytest.fixture(scope="session")
def king_raw(root):
    return pd.read_csv(root / "data" / "raw" / "kc_house_data.csv", dtype={"id": "string", "zipcode": "string"})
