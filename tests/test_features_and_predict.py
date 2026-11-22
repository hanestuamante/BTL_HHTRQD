"""F12: cùng dữ liệu raw cho cùng đặc trưng/dự báo qua luồng chính thức; schema sai báo lỗi rõ."""
import numpy as np
import pandas as pd
import pytest

from bds_valuation.features import FEATURES, SchemaError, engineer_king_features, validate_king_raw


def test_engineered_features_match_etl(king_clean):
    d = engineer_king_features(king_clean)
    # house_age và Haversine phải khớp đúng giá trị Nhiệm vụ 2 đã tính
    assert np.allclose(d["house_age"], king_clean["house_age"])
    assert np.allclose(d["distance_to_center_km"], king_clean["distance_to_center_km"], atol=1e-9)
    assert d["month_index"].between(0, 12).all()
    assert set(FEATURES) <= set(d.columns)


def test_raw_and_clean_give_same_features(king_raw, king_clean):
    raw = king_raw.drop_duplicates()
    raw = raw[raw["bedrooms"] < 30]                       # dòng 33 phòng ngủ bị cách ly ở ETL
    a = engineer_king_features(raw.head(300))[FEATURES].reset_index(drop=True)
    b = engineer_king_features(king_clean.head(300))[FEATURES].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_missing_column_raises(king_clean):
    with pytest.raises(SchemaError, match="Thiếu trường bắt buộc"):
        validate_king_raw(king_clean.drop(columns=["grade"]))


def test_wrong_type_raises(king_clean):
    bad = king_clean.head(5).copy()
    bad["sqft_living"] = bad["sqft_living"].astype(object)
    bad.loc[bad.index[0], "sqft_living"] = "abc"
    with pytest.raises(SchemaError, match="không phải số"):
        validate_king_raw(bad)


def test_area_relation_enforced(king_clean):
    bad = king_clean.head(5).copy()
    bad["sqft_living"] = bad["sqft_living"] + 100
    with pytest.raises(SchemaError, match="sqft_above"):
        validate_king_raw(bad)


def test_bad_zipcode_raises(king_clean):
    bad = king_clean.head(3).copy()
    bad["zipcode"] = "98A01"
    with pytest.raises(SchemaError, match="zipcode"):
        validate_king_raw(bad)


def test_predict_api_on_saved_bundle(root, king_raw):
    path = root / "models" / "model.pkl"
    if not path.exists():
        pytest.skip("Chưa có models/model.pkl")
    from bds_valuation.predict import load_bundle, predict_prices
    bundle = load_bundle(path)
    sample = king_raw[king_raw["bedrooms"] < 30].head(50)
    out1 = predict_prices(sample, bundle)
    out2 = predict_prices(sample.copy(), bundle)
    assert np.array_equal(out1["predicted_price"], out2["predicted_price"])
    assert (out1["predicted_price"] > 0).all()
    assert not out1["ngoai_khoang_thoi_gian_huan_luyen"].any()
