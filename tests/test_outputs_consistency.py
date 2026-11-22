"""Hồi quy trên artifact đã lưu: residual, top 20, bảng ngưỡng, model.pkl và summary phải thống nhất với nhau."""
import json

import numpy as np
import pandas as pd
import pytest

from bds_valuation import selection as S


@pytest.fixture(scope="module")
def t4(root):
    t = root / "outputs" / "task4" / "tables"
    if not (t / "king_oof_predictions.csv").exists():
        pytest.skip("Chưa chạy scripts/task4_modeling.py")
    return t


@pytest.fixture(scope="module")
def val(t4):
    return pd.read_csv(t4 / "king_oof_predictions.csv", dtype={"id": "string", "zipcode": "string"})


def test_residual_formulas(val):
    assert len(val) == 21612
    assert np.allclose(val["residual"], (val["price"] - val["predicted_price"]).round(0))
    assert np.allclose(val["residual_pct"], val["price"] / val["predicted_price"] - 1)
    others = [c for c in ("residual_pct_rf", "residual_pct_lr", "residual_pct_xgb") if c in val][:2]
    assert np.allclose(val["residual_pct_conservative"], val[["residual_pct", *others]].max(axis=1))
    assert (val.groupby("id")["is_latest_sale"].sum() == 1).all()


def test_top20_follows_rules(val, t4):
    top = pd.read_csv(t4 / "top20_candidates_below_prediction_king.csv", dtype={"id": "string"})
    others = tuple(c for c in ("residual_pct_rf", "residual_pct_lr", "residual_pct_xgb") if c in val)[:2]
    pool = S.base_pool(val)
    expected = S.rank_candidates(pool[S.recommended_mask(pool, others=others)])
    assert list(top["id"]) == list(expected["id"])
    assert top["id"].is_unique and len(top) == S.N_CANDIDATES
    assert top["below_prediction_conservative_pct"].is_monotonic_decreasing
    assert "upside_usd" not in top.columns            # F05: không còn cột ngụ ý lợi nhuận


def test_threshold_table(val, t4):
    thr = pd.read_csv(t4 / "sensitivity_threshold.csv")
    pool = S.base_pool(val)
    for _, r in thr.iterrows():
        assert (pool["residual_pct"] <= -r["Nguong_%"] / 100).sum() == r["So_can_ung_vien"]


def test_summary_bundle_agree(root, t4):
    summary = json.loads((t4 / "task4_summary.json").read_text(encoding="utf-8"))
    from bds_valuation.predict import load_bundle
    bundle = load_bundle(root / "models" / "model.pkl")       # load_bundle kiểm tra tên ↔ kiểu estimator
    assert bundle["model_name"] == summary["best_model"]
    met = pd.read_csv(t4 / "model_metrics_mape_report.csv")
    row = met[(met["Thi_truong"] == "King County") & (met["Mo_hinh"] == summary["best_model"])].iloc[0]
    assert row["Chon_bang_CV_train"] in (True, "True")
    assert bundle["test_metrics"]["MAPE_%"] == pytest.approx(row["MAPE_%"])
    tb = json.loads((t4 / "temporal_backtest.json").read_text(encoding="utf-8"))
    assert tb["past_date_range"][1] < tb["cutoff"] <= tb["future_date_range"][0]
