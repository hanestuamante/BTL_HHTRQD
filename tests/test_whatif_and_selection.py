"""F06: what-if giữ quan hệ diện tích; F05/F08: quy tắc chọn ứng viên."""
import numpy as np
import pandas as pd
import pytest

from bds_valuation import selection as S
from bds_valuation.features import engineer_king_features
from bds_valuation.whatif import SCENARIOS, apply_scenario, check_area_invariant, out_of_domain_share


@pytest.fixture(scope="module")
def X(king_clean):
    return engineer_king_features(king_clean.head(2000))


def test_every_scenario_keeps_area_relation(X):
    assert (X["sqft_basement"] > 0).any() and (X["sqft_basement"] == 0).any()
    for name in SCENARIOS:
        check_area_invariant(apply_scenario(name, X))


def test_above_ground_scenario_with_and_without_basement(X):
    out = apply_scenario("Diện tích trên mặt đất +10% (hầm giữ nguyên)", X)
    has, no = X["sqft_basement"] > 0, X["sqft_basement"] == 0
    assert np.allclose(out.loc[no, "sqft_living"], X.loc[no, "sqft_living"] * 1.1)
    assert np.allclose(out["sqft_basement"], X["sqft_basement"])
    assert (out.loc[has, "sqft_living"] < X.loc[has, "sqft_living"] * 1.1).all()   # tổng tăng < 10% khi có hầm
    tot = apply_scenario("Tổng diện tích ở +10% (trên mặt đất và hầm cùng tỷ lệ)", X)
    assert np.allclose(tot["sqft_living"], X["sqft_living"] * 1.1)


def test_broken_scenario_is_caught(X):
    bad = X.assign(sqft_living=X["sqft_living"] * 1.1, sqft_above=X["sqft_above"] * 1.1)   # lỗi cũ F06
    with pytest.raises(AssertionError):
        check_area_invariant(bad[bad["sqft_basement"] > 0])


def test_out_of_domain_flag(X):
    assert out_of_domain_share(X, X) == 0.0
    moved = apply_scenario("Thời điểm bán +6 tháng", X)
    assert out_of_domain_share(moved, X) > 0


def _val():
    rng = np.random.default_rng(0)
    n = 60
    v = pd.DataFrame({
        "id": [f"p{i//2}" for i in range(n)],                    # mỗi tài sản 2 giao dịch
        "date": pd.to_datetime(["2014-06-01", "2015-03-01"] * (n // 2)),
        "price": rng.uniform(2e5, 9e5, n), "predicted_price": rng.uniform(3e5, 9e5, n),
        "house_age": rng.integers(0, 50, n), "condition": rng.integers(1, 6, n),
        "zero_room_flag": (rng.random(n) < 0.1).astype(int),
        "residual_pct": rng.uniform(-0.7, 0.3, n), "residual_pct_rf": rng.uniform(-0.7, 0.3, n),
        "residual_pct_lr": rng.uniform(-0.7, 0.3, n)})
    v["is_latest_sale"] = (v["date"] == v.groupby("id")["date"].transform("max")).astype(int)
    v["residual_pct_conservative"] = S.conservative_key(v)
    return v


def test_selection_rules():
    v = _val()
    pool = S.base_pool(v)
    assert pool["id"].is_unique and (pool["condition"] >= 3).all() and (pool["zero_room_flag"] == 0).all()
    rec = pool[S.recommended_mask(pool)]
    assert (rec["residual_pct"].between(S.ANOMALY_CAP, S.BELOW_THRESHOLD)).all()
    assert (rec[list(S.RESID_COLS)] <= S.BELOW_THRESHOLD).all().all() and (rec["house_age"] > 0).all()
    top = S.rank_candidates(rec)
    assert top["residual_pct_conservative"].is_monotonic_increasing
    assert np.allclose(top["gap_to_prediction_usd"], (top["predicted_price"] - top["price"]).round(0))
    assert top["Hang"].tolist() == list(range(1, len(top) + 1))


def test_candidate_ids_reproduces_main_list():
    v = _val()
    pool = S.base_pool(v)
    main = S.rank_candidates(pool[S.recommended_mask(pool)])
    ids = S.candidate_ids({"m": v["residual_pct"], "o1": v["residual_pct_rf"], "o2": v["residual_pct_lr"]},
                          pool.index, v["house_age"], v["id"])
    assert set(ids) == set(main["id"])


def test_membership_frequency():
    f = S.membership_frequency({"a": ["x", "y"], "b": ["x", "z"], "c": ["x"]}, ["x", "y"])
    row = f.set_index("id")
    assert row.loc["x", "So_lan_xuat_hien"] == 3 and row.loc["x", "Nhom_loi_moi_bien_the"] == 1
    assert row.loc["z", "Trong_danh_sach_chinh"] == 0 and row.loc["y", "Ty_le_xuat_hien_%"] == pytest.approx(100 / 3)
