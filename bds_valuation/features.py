"""Tạo biến cho mô hình King County từ trường gốc, có kiểm tra schema (F12).

Một hàm ``engineer_king_features`` dùng chung cho huấn luyện và dự báo nên biến luôn được tạo
giống nhau. Các công thức khớp ``scripts/prepare_data.py`` (house_age, Haversine) và mục 1 của
``scripts/task4_modeling.py`` (is_renovated, years_since_update, month_index).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CENTER = (47.6062, -122.3321)          # mốc trung tâm Seattle do nhóm quy ước (xem metadata/etl_summary.json)
EARTH_RADIUS_KM = 6371.0088
MONTH_ZERO = (2014, 5)                   # month_index = 0 tại 05/2014, tháng đầu của dữ liệu

# Trường gốc người dùng phải cung cấp để dự báo (đúng tên trong kc_house_data.csv / king_county_clean.csv).
RAW_NUMERIC = ["bedrooms", "bathrooms", "sqft_living", "sqft_lot", "floors", "waterfront", "view",
               "condition", "grade", "sqft_above", "sqft_basement", "yr_built", "yr_renovated",
               "lat", "long", "sqft_living15", "sqft_lot15"]
RAW_REQUIRED = ["date", "zipcode", *RAW_NUMERIC]

NUM_FEATURES = ["bedrooms", "bathrooms", "sqft_living", "sqft_lot", "floors", "waterfront", "view",
                "condition", "grade", "sqft_above", "sqft_basement", "house_age", "is_renovated",
                "years_since_update", "lat", "long", "distance_to_center_km", "sqft_living15",
                "sqft_lot15", "month_index"]
CAT_FEATURES = ["zipcode"]
FEATURES = NUM_FEATURES + CAT_FEATURES
LOG_COLS = ["sqft_living", "sqft_lot", "sqft_above", "sqft_living15", "sqft_lot15", "distance_to_center_km"]
LEAKAGE = {"price", "price_per_sqft", "price_iqr_outlier"}
assert not LEAKAGE & set(FEATURES)


class SchemaError(ValueError):
    """Dữ liệu đầu vào thiếu trường hoặc sai kiểu/miền giá trị."""


def haversine_km(lat, lon, center=CENTER):
    lat, lon, clat, clon = map(np.radians, [np.asarray(lat, float), np.asarray(lon, float), *center])
    a = np.sin((lat - clat) / 2) ** 2 + np.cos(lat) * np.cos(clat) * np.sin((lon - clon) / 2) ** 2
    return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def validate_king_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Kiểm tra trường bắt buộc, kiểu và miền; trả về bản sao đã chuẩn hóa kiểu."""
    if not isinstance(df, pd.DataFrame):
        raise SchemaError("Đầu vào phải là pandas.DataFrame.")
    missing = [c for c in RAW_REQUIRED if c not in df.columns]
    if missing:
        raise SchemaError(f"Thiếu trường bắt buộc: {missing}")
    out = df.copy()
    errors = []
    for c in RAW_NUMERIC:
        conv = pd.to_numeric(out[c], errors="coerce")
        bad = conv.isna() & out[c].notna()
        if bad.any():
            errors.append(f"{c}: {int(bad.sum())} giá trị không phải số (vd {out.loc[bad, c].iloc[0]!r})")
        if conv.isna().any():
            errors.append(f"{c}: {int(conv.isna().sum())} giá trị thiếu")
        out[c] = conv.astype(float)
    dates = pd.to_datetime(out["date"], errors="coerce")
    if dates.isna().any():
        errors.append(f"date: {int(dates.isna().sum())} ngày không đọc được")
    out["date"] = dates
    out["zipcode"] = out["zipcode"].astype("string").str.strip()
    if out["zipcode"].isna().any() or (~out["zipcode"].fillna("").str.fullmatch(r"\d{5}")).any():
        errors.append("zipcode: phải là chuỗi 5 chữ số")
    if errors:
        raise SchemaError("; ".join(errors))
    checks = {
        "sqft_living > 0": out["sqft_living"] > 0,
        "sqft_lot > 0": out["sqft_lot"] > 0,
        "sqft_above >= 0 và sqft_basement >= 0": (out["sqft_above"] >= 0) & (out["sqft_basement"] >= 0),
        "sqft_living = sqft_above + sqft_basement": np.isclose(out["sqft_living"], out["sqft_above"] + out["sqft_basement"]),
        "condition trong 1..5": out["condition"].between(1, 5),
        "grade trong 1..13": out["grade"].between(1, 13),
        "view trong 0..4": out["view"].between(0, 4),
        "waterfront là 0/1": out["waterfront"].isin([0, 1]),
        "lat/long trong vùng King County": out["lat"].between(47.0, 48.0) & out["long"].between(-123.0, -121.0),
    }
    bad = [f"{k} ({int((~v).sum())} dòng sai)" for k, v in checks.items() if not v.all()]
    if bad:
        raise SchemaError("Sai miền giá trị: " + "; ".join(bad))
    return out


def engineer_king_features(df: pd.DataFrame, validate: bool = True) -> pd.DataFrame:
    """Trả về DataFrame có đủ ``FEATURES`` (đúng thứ tự), tạo từ trường gốc."""
    d = validate_king_raw(df) if validate else df.copy()
    d["date"] = pd.to_datetime(d["date"])
    sale_year = d["date"].dt.year
    d["house_age"] = (sale_year - d["yr_built"]).clip(lower=0)
    d["is_renovated"] = (d["yr_renovated"] > 0).astype(int)
    d["years_since_update"] = (sale_year - d[["yr_built", "yr_renovated"]].max(axis=1)).clip(lower=0)
    d["month_index"] = (sale_year - MONTH_ZERO[0]) * 12 + d["date"].dt.month - MONTH_ZERO[1]
    d["distance_to_center_km"] = haversine_km(d["lat"], d["long"])
    d["zipcode"] = d["zipcode"].astype("string")
    return d


def load_king_clean(path) -> pd.DataFrame:
    """Đọc CSV sạch của Nhiệm vụ 2 đúng kiểu và tạo biến mô hình."""
    king = pd.read_csv(path, dtype={"id": "string", "zipcode": "string"})
    king = engineer_king_features(king, validate=True)
    return king
