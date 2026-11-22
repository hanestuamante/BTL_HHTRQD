"""Phân tách tài sản, backtest thời gian độc lập (F02) và điền thiếu Ames học trên train (F01)."""
import numpy as np
import pandas as pd
import pytest

from bds_valuation.ames import GroupMedianImputer, ames_feature_lists, load_ames_for_modeling
from bds_valuation.evaluation import group_split, temporal_split
from bds_valuation.features import engineer_king_features


def test_group_split_no_property_overlap(king_clean):
    tr, te = group_split(king_clean, king_clean["price"], king_clean["id"])
    assert not set(king_clean["id"].iloc[tr]) & set(king_clean["id"].iloc[te])
    assert abs(len(te) / len(king_clean) - 0.2) < 0.02


def test_temporal_split_future_isolated(king_clean):
    d = engineer_king_features(king_clean)
    s = temporal_split(d["date"], d["id"], cutoff="2015-02-01", val_months=3)
    dates, ids = d["date"].reset_index(drop=True), d["id"].reset_index(drop=True)
    cut = pd.Timestamp("2015-02-01")
    # Không dòng tương lai nào nằm trong dữ liệu tinh chỉnh/chọn mô hình
    tuning = np.concatenate([s.inner_train_idx, s.inner_val_idx, s.past_idx])
    assert (dates.iloc[tuning] < cut).all()
    assert (dates.iloc[s.future_idx] >= cut).all()
    assert not set(ids.iloc[s.future_idx]) & set(ids.iloc[s.past_idx])
    assert (dates.iloc[s.inner_train_idx] < pd.Timestamp("2014-11-01")).all()
    assert not set(ids.iloc[s.inner_val_idx]) & set(ids.iloc[s.inner_train_idx])
    assert s.info["future_rows"] == len(s.future_idx) > 1000


def _toy():
    return pd.DataFrame({"neighborhood": ["A", "A", "A", "B", "B", "C"],
                         "lot": [10.0, np.nan, 30.0, 100.0, np.nan, np.nan],
                         "cat": list("xyzxyz")})


def test_group_median_imputer_learns_from_train_only():
    tr = _toy()
    imp = GroupMedianImputer("neighborhood", ["lot"]).fit(tr)
    te1 = pd.DataFrame({"neighborhood": ["A", "B", "Z"], "lot": [np.nan, np.nan, np.nan], "cat": list("xyz")})
    te2 = te1.assign(lot=[1e6, np.nan, 5.0])           # đổi tập test
    imp_again = GroupMedianImputer("neighborhood", ["lot"]).fit(tr)
    assert imp.group_medians_.equals(imp_again.group_medians_)   # test không ảnh hưởng trung vị đã học
    out = imp.transform(te1)
    assert out["lot"].tolist() == [20.0, 100.0, 30.0]            # nhóm A, B; nhóm lạ Z -> trung vị toàn bộ train
    assert imp.transform(te2)["lot"].tolist() == [1e6, 100.0, 5.0]
    # nhóm C có trong train nhưng toàn NaN -> fallback trung vị toàn bộ train
    assert imp.transform(pd.DataFrame({"neighborhood": ["C"], "lot": [np.nan], "cat": ["x"]}))["lot"].iloc[0] == 30.0


def test_ames_learned_imputations_restored(root):
    ames, cols = load_ames_for_modeling(root / "data/processed/ames_clean.csv", root / "metadata/imputation_audit.csv")
    audit = pd.read_csv(root / "metadata/imputation_audit.csv", dtype=str)
    learned = audit[(audit.dataset == "ames") & audit.rule.str.startswith(("Missing thực: trung vị", "Năm gara ngoài"))]
    assert int(ames[cols].isna().sum().sum()) == len(learned)
    assert "lot_frontage" in cols
    # Điền cấu trúc (No_basement, No_garage...) vẫn giữ nguyên
    assert ames["bsmt_qual"].notna().all() and ames["garage_type"].notna().all()
    feats, nums, cats = ames_feature_lists(ames)
    assert "sale_type" not in feats and "price" not in feats and not any(c.endswith("_imputed") for c in feats)


def test_ames_pipeline_imputer_fit_on_train(root):
    from bds_valuation.ames import make_ames_model
    ames, cols = load_ames_for_modeling(root / "data/processed/ames_clean.csv", root / "metadata/imputation_audit.csv")
    feats, nums, cats = ames_feature_lists(ames)
    tr, te = ames.iloc[:2000], ames.iloc[2000:]
    m = make_ames_model("lr", nums, cats).fit(tr[feats], tr["price"])
    learned = m.regressor_.named_steps["imp"].group_medians_
    expected = tr[feats].groupby("neighborhood")[nums].median()
    pd.testing.assert_frame_equal(learned, expected)
    assert np.isfinite(m.predict(te[feats])).all()
