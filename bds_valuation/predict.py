"""Luồng dự báo chính thức cho ``models/model.pkl`` (F12).

Dùng trong Python::

    from bds_valuation.predict import load_bundle, predict_prices
    bundle = load_bundle()                       # tự tìm models/model.pkl
    out = predict_prices(df_raw, bundle)         # df_raw có các trường gốc như kc_house_data.csv

Dùng dòng lệnh::

    python -m bds_valuation.predict data/raw/kc_house_data.csv outputs/du_bao.csv

Giới hạn: mô hình học trên giao dịch King County 05/2014–05/2015. Dự báo cho thời điểm hoặc khu
vực khác là ngoại suy, chưa có bằng chứng đánh giá cho thị trường hiện tại.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .features import FEATURES, RAW_REQUIRED, engineer_king_features
from .models import check_bundle_consistency
from .paths import find_project_root

TRAIN_MONTH_RANGE = (0, 12)    # 05/2014 .. 05/2015


def load_bundle(path: str | Path | None = None) -> dict:
    path = Path(path) if path else find_project_root(Path(__file__)) / "models" / "model.pkl"
    bundle = joblib.load(path)
    check_bundle_consistency(bundle)
    return bundle


def predict_prices(df_raw: pd.DataFrame, bundle: dict | None = None) -> pd.DataFrame:
    """Kiểm tra schema, tạo biến đúng như lúc huấn luyện rồi dự báo giá (USD)."""
    bundle = bundle or load_bundle()
    X = engineer_king_features(df_raw, validate=True)
    if list(bundle["features"]) != FEATURES:
        raise ValueError("Danh sách biến trong bundle khác phiên bản package; huấn luyện lại hoặc dùng đúng phiên bản.")
    pred = bundle["model"].predict(X[FEATURES])
    out = df_raw.copy()
    out["predicted_price"] = np.round(pred, 0)
    out["month_index"] = X["month_index"].to_numpy()
    out["ngoai_khoang_thoi_gian_huan_luyen"] = ~X["month_index"].between(*TRAIN_MONTH_RANGE).to_numpy()
    if "price" in out:
        out["residual_pct"] = out["price"] / out["predicted_price"] - 1
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dự báo giá King County bằng models/model.pkl")
    ap.add_argument("input_csv")
    ap.add_argument("output_csv")
    ap.add_argument("--model", default=None)
    a = ap.parse_args(argv)
    df = pd.read_csv(a.input_csv, dtype={"id": "string", "zipcode": "string"})
    out = predict_prices(df, load_bundle(a.model))
    Path(a.output_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output_csv, index=False)
    print(f"Đã dự báo {len(out):,} dòng -> {a.output_csv}. Trường bắt buộc: {RAW_REQUIRED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
