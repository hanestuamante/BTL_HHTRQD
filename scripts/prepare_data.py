"""Nhiệm vụ 2: ETL có lưu nguồn, dấu vết và kiểm tra dữ liệu nhà ở.

Chạy từ thư mục gốc: python scripts/prepare_data.py
Thêm --refresh để tải lại các nguồn; mặc định dùng raw đã lưu và kiểm SHA256.
"""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import re
import urllib.request

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "king_county": {
        "file": "kc_house_data.csv",
        "url": "https://raw.githubusercontent.com/jmatth11/King-County-House-Data-Set/master/kc_house_data.csv",
        "origin": "https://www.kaggle.com/datasets/harlfoxem/housesalesprediction",
        "note": "Bản sao CSV công khai của dữ liệu Kaggle; không phải tải trực tiếp từ Kaggle.",
    },
    "ames": {
        "file": "AmesHousing.txt",
        "url": "https://jse.amstat.org/v19n3/decock/AmesHousing.txt",
        "origin": "https://jse.amstat.org/v19n3/decock.pdf",
        "note": "Dữ liệu gốc kèm bài báo De Cock 2011.",
    },
    "ames_documentation": {
        "file": "Ames_DataDocumentation.txt",
        "url": "https://jse.amstat.org/v19n3/decock/DataDocumentation.txt",
        "origin": "https://jse.amstat.org/v19n3/decock/DataDocumentation.txt",
        "note": "Từ điển gốc gồm mã danh mục và ý nghĩa NA.",
    },
}

AMES_DESCRIPTIONS = {
    "order": "Số thứ tự quan sát trong nguồn", "pid": "Mã thửa đất",
    "ms_subclass": "Mã loại hình nhà ở", "ms_zoning": "Phân khu sử dụng đất",
    "lot_frontage": "Chiều dài mặt tiền giáp đường", "lot_area": "Diện tích thửa đất",
    "street": "Loại đường tiếp cận", "alley": "Loại đường hẻm tiếp cận",
    "lot_shape": "Hình dạng thửa đất", "land_contour": "Địa hình thửa đất",
    "utilities": "Hệ thống tiện ích công cộng", "lot_config": "Vị trí và cấu hình lô đất",
    "land_slope": "Độ dốc đất", "neighborhood": "Mã khu dân cư Ames",
    "condition_1": "Điều kiện lân cận thứ nhất", "condition_2": "Điều kiện lân cận thứ hai",
    "bldg_type": "Loại công trình nhà ở", "house_style": "Kiểu bố trí tầng của nhà",
    "overall_qual": "Chất lượng vật liệu và hoàn thiện tổng thể từ 1 đến 10",
    "overall_cond": "Tình trạng tổng thể từ 1 đến 10", "year_built": "Năm xây dựng",
    "year_remod_add": "Năm cải tạo hoặc mở rộng", "roof_style": "Kiểu mái",
    "roof_matl": "Vật liệu mái", "exterior_1st": "Vật liệu tường ngoài chính",
    "exterior_2nd": "Vật liệu tường ngoài bổ sung", "mas_vnr_type": "Loại lớp ốp xây ngoài",
    "mas_vnr_area": "Diện tích lớp ốp xây ngoài", "exter_qual": "Chất lượng hoàn thiện bên ngoài",
    "exter_cond": "Tình trạng bên ngoài", "foundation": "Loại móng",
    "bsmt_qual": "Chất lượng chiều cao tầng hầm", "bsmt_cond": "Tình trạng tầng hầm",
    "bsmt_exposure": "Mức tiếp xúc bên ngoài của tầng hầm", "bsmtfin_type_1": "Loại hoàn thiện tầng hầm phần 1",
    "bsmtfin_sf_1": "Diện tích hoàn thiện tầng hầm phần 1", "bsmtfin_type_2": "Loại hoàn thiện tầng hầm phần 2",
    "bsmtfin_sf_2": "Diện tích hoàn thiện tầng hầm phần 2", "bsmt_unf_sf": "Diện tích tầng hầm chưa hoàn thiện",
    "total_bsmt_sf": "Tổng diện tích tầng hầm", "heating": "Loại hệ thống sưởi",
    "heating_qc": "Chất lượng hệ thống sưởi", "central_air": "Có điều hòa trung tâm",
    "electrical": "Loại hệ thống điện", "1st_flr_sf": "Diện tích tầng một",
    "2nd_flr_sf": "Diện tích tầng hai", "low_qual_fin_sf": "Diện tích hoàn thiện chất lượng thấp",
    "gr_liv_area": "Diện tích sinh hoạt trên mặt đất", "bsmt_full_bath": "Số phòng tắm đầy đủ tầng hầm",
    "bsmt_half_bath": "Số phòng vệ sinh nửa tầng hầm", "full_bath": "Số phòng tắm đầy đủ trên mặt đất",
    "half_bath": "Số phòng vệ sinh nửa trên mặt đất", "bedroom_abvgr": "Số phòng ngủ trên mặt đất",
    "kitchen_abvgr": "Số bếp trên mặt đất", "kitchen_qual": "Chất lượng bếp",
    "totrms_abvgrd": "Tổng số phòng trên mặt đất không kể phòng tắm", "functional": "Mức độ đáp ứng công năng",
    "fireplaces": "Số lò sưởi", "fireplace_qu": "Chất lượng lò sưởi",
    "garage_type": "Vị trí và loại gara", "garage_yr_blt": "Năm xây gara hoặc 0 nếu không có gara",
    "garage_finish": "Mức độ hoàn thiện bên trong gara", "garage_cars": "Sức chứa gara tính bằng số xe",
    "garage_area": "Diện tích gara", "garage_qual": "Chất lượng gara", "garage_cond": "Tình trạng gara",
    "paved_drive": "Mức độ lát lối xe vào", "wood_deck_sf": "Diện tích sàn gỗ ngoài trời",
    "open_porch_sf": "Diện tích hiên mở", "enclosed_porch": "Diện tích hiên khép kín",
    "3ssn_porch": "Diện tích hiên sử dụng ba mùa", "screen_porch": "Diện tích hiên có lưới chắn",
    "pool_area": "Diện tích bể bơi", "pool_qc": "Chất lượng bể bơi", "fence": "Chất lượng hàng rào",
    "misc_feature": "Hạng mục bổ sung khác", "misc_val": "Giá trị hạng mục bổ sung",
    "mo_sold": "Tháng bán", "yr_sold": "Năm bán", "sale_type": "Loại hình giao dịch",
    "sale_condition": "Điều kiện giao dịch", "sale_price": "Giá bán thực tế",
}
KING_DESCRIPTIONS = {
    "id": "Mã bất động sản; có thể xuất hiện nhiều giao dịch", "date": "Ngày bán định dạng ISO 8601",
    "price": "Giá bán thực tế", "bedrooms": "Số phòng ngủ", "bathrooms": "Số phòng tắm tương đương",
    "sqft_living": "Tổng diện tích sinh hoạt bên trong nhà", "sqft_lot": "Diện tích thửa đất",
    "floors": "Số tầng", "waterfront": "Bất động sản tiếp giáp mặt nước mã 0 hoặc 1",
    "view": "Điểm chất lượng cảnh quan từ 0 đến 4", "condition": "Điểm tình trạng nhà từ 1 đến 5",
    "grade": "Cấp chất lượng xây dựng King County; 7 là Average; 13 là Mansion",
    "sqft_above": "Diện tích nhà trên mặt đất", "sqft_basement": "Diện tích tầng hầm",
    "yr_built": "Năm xây dựng", "yr_renovated": "Năm cải tạo hoặc 0 nếu chưa ghi nhận cải tạo",
    "zipcode": "Mã bưu chính giữ kiểu chuỗi", "lat": "Vĩ độ", "long": "Kinh độ",
    "sqft_living15": "Diện tích sinh hoạt bổ sung do nguồn cung cấp; hậu tố 15 cần đối chiếu nguồn gốc trước diễn giải",
    "sqft_lot15": "Diện tích lô đất bổ sung do nguồn cung cấp; hậu tố 15 cần đối chiếu nguồn gốc trước diễn giải",
}
DERIVED_DESCRIPTIONS = {
    "source_row_id": "Số dòng dữ liệu gốc bắt đầu từ 1 không kể tiêu đề; khóa truy vết giao dịch",
    "sale_year": "Năm bán trích từ ngày bán", "price": "Bản sao sale_price của Ames để dùng cùng giao diện",
    "sqft_living": "Bản sao gr_liv_area của Ames; diện tích trên mặt đất khác phạm vi King County",
    "raw_house_age": "Năm bán trừ năm xây dựng trước khi xử lý giá trị âm",
    "house_age": "Tuổi nhà tại năm bán bằng max năm bán trừ năm xây dựng và 0",
    "age_capped_zero": "Cờ 1 khi tuổi tính ban đầu âm và được đặt bằng 0",
    "price_per_sqft": "Giá bán chia diện tích sinh hoạt; biến có chứa thông tin giá mục tiêu",
    "distance_to_center_km": "Khoảng cách đường chim bay Haversine đến điểm quy ước Seattle 47.6062 -122.3321; Ames không có tọa độ nên để thiếu",
    "distance_available": "Cờ 1 nếu có tọa độ thực để tính khoảng cách; 0 đối với Ames",
    "price_iqr_outlier": "Cờ giá nằm ngoài Q1 trừ 1.5IQR hoặc Q3 cộng 1.5IQR; giữ lại dữ liệu",
    "area_iqr_outlier": "Cờ diện tích sinh hoạt nằm ngoài ngưỡng 1.5IQR; giữ lại dữ liệu",
    "unusual_area_gt4000": "Cờ Ames diện tích trên mặt đất lớn hơn 4000 sqft theo gợi ý kiểm tra của De Cock; không tự động loại",
    "zero_room_flag": "Cờ King County phòng ngủ hoặc phòng tắm bằng 0; giữ để kiểm tra",
    "has_any_imputation": "Cờ 1 nếu hàng có ô missing hoặc sai miền được thay thế kể cả xác nhận không có tiện ích",
    "has_true_imputation": "Cờ 1 nếu hàng có missing thực hoặc năm gara sai miền được thay, không tính NA cấu trúc xác nhận không có tiện ích",
}


def snake(name):
    return "sale_price" if name == "SalePrice" else re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def acquire(refresh=False):
    manifest_path = ROOT / "metadata/sources.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    records = {}
    for key, entry in SOURCES.items():
        path = ROOT / "data/raw" / entry["file"]
        fetched = refresh or not path.exists()
        if fetched:
            with urllib.request.urlopen(entry["url"], timeout=45) as response:
                content = response.read()
            if len(content) < 1000:
                raise ValueError(f"Nguồn quá nhỏ hoặc không hợp lệ: {entry['url']}")
            path.write_bytes(content)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if not fetched and key in previous:
            assert checksum == previous[key]["sha256"], f"Raw đã thay đổi: {path}"
        records[key] = dict(entry, sha256=checksum, bytes=path.stat().st_size,
                            downloaded_at_utc=(datetime.now(timezone.utc).isoformat() if fetched else previous.get(key, {}).get("downloaded_at_utc", datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())),
                            local_path=str(path.relative_to(ROOT)))
        downloaded = datetime.fromisoformat(records[key]["downloaded_at_utc"])
        records[key]["downloaded_at_vietnam"] = downloaded.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat()
    dump_json(manifest_path, records)
    return records


def haversine(lat, lon, center=(47.6062, -122.3321)):
    lat, lon, clat, clon = map(np.radians, [lat, lon, *center])
    a = np.sin((lat-clat)/2)**2 + np.cos(lat)*np.cos(clat)*np.sin((lon-clon)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def flag_iqr(series):
    q1, q3 = series.quantile([.25, .75])
    low, high = float(q1-1.5*(q3-q1)), float(q3+1.5*(q3-q1))
    return ((series < low) | (series > high)).astype("int8"), {"q1": float(q1), "q3": float(q3), "low": low, "high": high}


def impute(df, col, mask, values, rule, events):
    mask = mask.reindex(df.index).fillna(False)
    if not mask.any():
        return
    new_values = values.reindex(df.index).loc[mask] if isinstance(values, pd.Series) else values
    before = df.loc[mask, col].astype(object).where(df.loc[mask, col].notna(), "<MISSING>")
    df.loc[mask, col] = new_values
    flag = f"{col}_imputed"
    if flag not in df:
        df[flag] = np.int8(0)
    df.loc[mask, flag] = np.int8(1)
    for idx, old in before.items():
        new = df.at[idx, col]
        events.append({"dataset": "ames", "source_row_id": int(df.at[idx, "source_row_id"]), "column": col,
                       "before": str(old), "after": str(new), "rule": rule})


def by_neighborhood_median(df, col):
    return df.groupby("neighborhood", observed=True)[col].transform("median").fillna(df[col].median())


def prepare_king():
    raw = pd.read_csv(ROOT / "data/raw/kc_house_data.csv", dtype={"id": "string", "zipcode": "string"})
    assert raw.shape == (21613, 21), f"King schema không đúng: {raw.shape}"
    df = raw.copy()
    df.insert(0, "source_row_id", np.arange(1, len(df)+1))
    reasons = pd.Series("", index=df.index)
    invalid = (df.price <= 0) | (df.sqft_living <= 0) | (df.sqft_lot <= 0) | (df.bedrooms < 0) | (df.bathrooms < 0) | ~df.lat.between(-90,90) | ~df.long.between(-180,180)
    reasons.loc[invalid] = "invalid_domain"
    reasons.loc[df.bedrooms > 20] += "suspected_bedrooms_gt20;"
    reasons.loc[raw.duplicated()] += "exact_duplicate;"
    quarantine = df.loc[reasons.ne("")].copy()
    quarantine["quarantine_reason"] = reasons.loc[reasons.ne("")]
    quarantine.to_csv(ROOT / "data/processed/king_county_quarantine.csv", index=False)
    df = df.loc[reasons.eq("")].copy()
    df["date"] = pd.to_datetime(df.date, format="%Y%m%dT%H%M%S", errors="raise")
    df["sale_year"] = df.date.dt.year
    df["raw_house_age"] = df.sale_year-df.yr_built
    df["age_capped_zero"] = df.raw_house_age.lt(0).astype("int8")
    df["house_age"] = df.raw_house_age.clip(lower=0)
    df["price_per_sqft"] = df.price/df.sqft_living
    df["distance_to_center_km"] = haversine(df.lat, df.long)
    df["distance_available"] = np.int8(1)
    df["has_any_imputation"] = np.int8(0)
    df["has_true_imputation"] = np.int8(0)
    df["zero_room_flag"] = ((df.bedrooms == 0) | (df.bathrooms == 0)).astype("int8")
    df["price_iqr_outlier"], price_limits = flag_iqr(df.price)
    df["area_iqr_outlier"], area_limits = flag_iqr(df.sqft_living)
    df["date"] = df.date.dt.strftime("%Y-%m-%d")
    assert df.house_age.ge(0).all() and df.price_per_sqft.gt(0).all()
    assert df.distance_to_center_km.between(0, 150).all()
    assert df.id.nunique() < len(df), "Không được xóa giao dịch lặp theo ID nhà"
    assert not df.isna().any().any()
    df.to_csv(ROOT / "data/processed/king_county_clean.csv", index=False)
    return raw, df, {"raw_rows": len(raw), "raw_columns": len(raw.columns), "clean_rows": len(df), "clean_columns": len(df.columns),
                     "quarantined_rows": len(quarantine), "exact_duplicates_removed": int(raw.duplicated().sum()),
                     "unique_properties": int(df.id.nunique()), "repeat_transaction_rows_beyond_first": int(len(df)-df.id.nunique()),
                     "raw_date_min": df.date.min(), "raw_date_max": df.date.max(),
                     "age_capped_zero": int(df.age_capped_zero.sum()), "zero_room_flag": int(df.zero_room_flag.sum()),
                     "price_iqr_outliers": int(df.price_iqr_outlier.sum()), "area_iqr_outliers": int(df.area_iqr_outlier.sum()),
                     "iqr_limits": {"price": price_limits, "sqft_living": area_limits},
                     "center": {"label": "Điểm đại diện trung tâm Seattle do nhóm quy ước", "lat": 47.6062, "long": -122.3321},
                     "distance_formula": "Haversine; R=6371.0088 km; đường chim bay, không phải thời gian đi lại"}


def prepare_ames(events):
    # pandas mặc định đọc cả 'None' thành missing; ở đây chỉ NA và ô trống là missing.
    raw = pd.read_csv(ROOT / "data/raw/AmesHousing.txt", sep="\t", keep_default_na=False, na_values=["NA", ""], dtype={"PID": "string", "MS SubClass": "string"})
    assert raw.shape == (2930,82), f"Ames schema không đúng: {raw.shape}"
    assert raw["Mas Vnr Type"].eq("None").sum() > 1000
    df = raw.rename(columns=snake).copy()
    df.insert(0, "source_row_id", np.arange(1,len(df)+1))
    duplicate = raw.duplicated()
    invalid = df.sale_price.le(0) | df.gr_liv_area.le(0) | df.lot_area.le(0)
    quarantine = df.loc[duplicate | invalid].copy()
    quarantine["quarantine_reason"] = np.where(duplicate[duplicate | invalid], "exact_duplicate", "invalid_domain")
    quarantine.to_csv(ROOT / "data/processed/ames_quarantine.csv", index=False)
    df = df.loc[~(duplicate | invalid)].copy()
    original_cols = df.columns.copy()
    missing_true_before = int(df.isna().sum().sum())
    # Các NA cấu trúc được định nghĩa rõ trong từ điển gốc.
    for col in ["alley", "fence", "misc_feature"]:
        impute(df, col, df[col].isna(), "No_feature", "NA theo từ điển gốc nghĩa là không có tiện ích", events)
    impute(df, "fireplace_qu", df.fireplace_qu.isna() & df.fireplaces.eq(0), "No_fireplace", "Số lò sưởi bằng 0 xác nhận không có lò sưởi", events)
    impute(df, "pool_qc", df.pool_qc.isna() & df.pool_area.eq(0), "No_pool", "Diện tích bể bơi bằng 0 xác nhận không có bể bơi", events)
    no_basement = df.total_bsmt_sf.eq(0)
    for col in ["bsmt_qual", "bsmt_cond", "bsmt_exposure", "bsmtfin_type_1", "bsmtfin_type_2"]:
        impute(df, col, df[col].isna() & no_basement, "No_basement", "Tổng diện tích tầng hầm bằng 0 xác nhận không có tầng hầm", events)
    for col in ["bsmtfin_sf_1", "bsmtfin_sf_2", "bsmt_unf_sf", "bsmt_full_bath", "bsmt_half_bath"]:
        impute(df, col, df[col].isna() & no_basement, 0, "Tổng diện tích tầng hầm bằng 0 nên tiện ích tầng hầm bằng 0", events)
    no_garage = df.garage_type.isna() & df.garage_cars.eq(0) & df.garage_area.eq(0)
    for col in ["garage_type", "garage_finish", "garage_qual", "garage_cond"]:
        impute(df, col, df[col].isna() & no_garage, "No_garage", "Diện tích và sức chứa gara bằng 0 xác nhận không có gara", events)
    impute(df, "garage_yr_blt", df.garage_yr_blt.isna() & no_garage, 0, "Gara không tồn tại; 0 là sentinel không phải năm lịch", events)
    invalid_garage_year = df.garage_yr_blt.notna() & df.garage_yr_blt.ne(0) & ~df.garage_yr_blt.between(1800, df.yr_sold+1)
    # Không tự sửa 2207 thành 2007 vì không có bằng chứng bản ghi gốc.
    if invalid_garage_year.any():
        valid = df.garage_yr_blt.mask(invalid_garage_year | df.garage_yr_blt.eq(0))
        values = valid.groupby(df.neighborhood).transform("median").fillna(valid.median()).round()
        impute(df, "garage_yr_blt", invalid_garage_year, values, "Năm gara ngoài miền 1800 đến năm bán cộng 1; thay trung vị năm gara dương theo neighborhood", events)
    for col in original_cols:
        if not df[col].isna().any():
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            if col == "garage_yr_blt":
                valid = df[col].mask(df[col].eq(0))
                values = valid.groupby(df.neighborhood).transform("median").fillna(valid.median())
            else:
                values = by_neighborhood_median(df, col)
            if col != "lot_frontage":
                values = values.round()
            impute(df, col, df[col].isna(), values, "Missing thực: trung vị theo neighborhood; fallback trung vị toàn bộ, không dùng giá bán", events)
        else:
            impute(df, col, df[col].isna(), "Unknown", "Missing thực chưa đủ bằng chứng không có tiện ích; giữ nhãn Unknown", events)
    imputation_flags = [c for c in df if c.endswith("_imputed")]
    df["has_any_imputation"] = df[imputation_flags].any(axis=1).astype("int8")
    true_ids = {e["source_row_id"] for e in events if e["rule"].startswith(("Missing thực", "Năm gara ngoài"))}
    df["has_true_imputation"] = df.source_row_id.isin(true_ids).astype("int8")
    df["price"] = df.sale_price
    df["sqft_living"] = df.gr_liv_area
    df["raw_house_age"] = df.yr_sold-df.year_built
    df["age_capped_zero"] = df.raw_house_age.lt(0).astype("int8")
    df["house_age"] = df.raw_house_age.clip(lower=0)
    df["price_per_sqft"] = df.price/df.sqft_living
    df["distance_to_center_km"] = np.nan
    df["distance_available"] = np.int8(0)
    df["price_iqr_outlier"], price_limits = flag_iqr(df.price)
    df["area_iqr_outlier"], area_limits = flag_iqr(df.sqft_living)
    df["unusual_area_gt4000"] = df.sqft_living.gt(4000).astype("int8")
    assert df.drop(columns="distance_to_center_km").notna().all().all()
    assert df.distance_to_center_km.isna().all() and df.house_age.ge(0).all()
    assert df.pid.is_unique and df.price_per_sqft.gt(0).all()
    assert "lat" not in df and "long" not in df and "zipcode" not in df
    df.to_csv(ROOT / "data/processed/ames_clean.csv", index=False)
    return raw, df, {"raw_rows": len(raw), "raw_columns": len(raw.columns), "clean_rows": len(df), "clean_columns": len(df.columns),
                     "quarantined_rows": len(quarantine), "exact_duplicates_removed": int(duplicate.sum()),
                     "unique_properties": int(df.pid.nunique()), "year_min": int(df.yr_sold.min()), "year_max": int(df.yr_sold.max()),
                     "original_missing_cells": missing_true_before, "remaining_missing_cells_original_fields": int(df[list(original_cols)].isna().sum().sum()),
                     "imputation_or_structural_fill_cells": len(events), "rows_with_any_fill": int(df.has_any_imputation.sum()),
                     "true_imputation_cells": sum(e["rule"].startswith(("Missing thực", "Năm gara ngoài")) for e in events),
                     "rows_with_true_imputation": int(df.has_true_imputation.sum()),
                     "invalid_garage_year_replaced": int(invalid_garage_year.sum()), "age_capped_zero": int(df.age_capped_zero.sum()),
                     "price_iqr_outliers": int(df.price_iqr_outlier.sum()), "area_iqr_outliers": int(df.area_iqr_outlier.sum()),
                     "unusual_area_gt4000": int(df.unusual_area_gt4000.sum()), "iqr_limits": {"price": price_limits, "sqft_living": area_limits},
                     "distance_note": "Không có lat long hoặc zipcode trong raw Ames; distance_to_center_km để NA, không nội suy tọa độ từ neighborhood.",
                     "literal_None_preserved_mas_vnr_type": int(raw["Mas Vnr Type"].eq("None").sum())}


def make_dictionary(raw, df, dataset, events):
    names = {snake(c) if dataset == "ames" else c: c for c in raw}
    desc = AMES_DESCRIPTIONS if dataset == "ames" else KING_DESCRIPTIONS
    rows = []
    area_fields = {"lot_area", "gr_liv_area", "mas_vnr_area", "garage_area", "enclosed_porch", "3ssn_porch", "screen_porch", "pool_area"}
    year_fields = {"yr_built", "yr_renovated", "year_built", "year_remod_add", "garage_yr_blt", "yr_sold", "sale_year"}
    count_units = {
        "bedrooms": "phòng ngủ", "bedroom_abvgr": "phòng ngủ", "bathrooms": "phòng tắm tương đương; phần lẻ 0.25, 0.5, 0.75",
        "floors": "tầng; có thể có nửa tầng", "full_bath": "phòng tắm đầy đủ", "half_bath": "phòng vệ sinh nửa",
        "bsmt_full_bath": "phòng tắm đầy đủ", "bsmt_half_bath": "phòng vệ sinh nửa", "kitchen_abvgr": "bếp",
        "totrms_abvgrd": "phòng không kể phòng tắm", "fireplaces": "lò sưởi", "garage_cars": "chỗ đỗ xe",
        "source_row_id": "số dòng gốc bắt đầu từ 1", "order": "số thứ tự quan sát", "mo_sold": "tháng từ 1 đến 12",
        "grade": "bậc chất lượng từ 1 đến 13", "condition": "điểm tình trạng từ 1 đến 5", "view": "điểm cảnh quan từ 0 đến 4",
        "overall_qual": "điểm chất lượng từ 1 đến 10", "overall_cond": "điểm tình trạng từ 1 đến 10",
        "id": "mã bất động sản dạng chuỗi", "pid": "mã thửa đất dạng chuỗi", "zipcode": "mã bưu chính dạng chuỗi",
        "waterfront": "0 hoặc 1", "central_air": "Y hoặc N", "date": "ngày ISO YYYY-MM-DD",
    }
    for c in df:
        original = c in names
        if c.endswith("_imputed"):
            meaning = f"Cờ ô {c[:-8]} được thay từ missing hoặc sai miền; xem imputation_audit.csv"
        else:
            meaning = desc.get(c, DERIVED_DESCRIPTIONS.get(c))
        assert meaning, f"Thiếu mô tả {dataset}.{c}"
        if c in {"price", "sale_price", "misc_val"}: unit="USD danh nghĩa tại thời điểm bán"
        elif c == "price_per_sqft": unit="USD/sqft"
        elif c == "distance_to_center_km": unit="km"
        elif c in {"lat", "long"}: unit="độ thập phân"
        elif c in {"house_age", "raw_house_age"}: unit="năm"
        elif c == "yr_renovated": unit="năm lịch YYYY; 0 là chưa ghi nhận cải tạo"
        elif c == "garage_yr_blt": unit="năm lịch YYYY; 0 là không có gara"
        elif c in year_fields: unit="năm lịch YYYY"
        elif c == "lot_frontage": unit="feet"
        elif c.startswith("sqft_") or c.endswith("_sf") or c in area_fields or re.match(r"bsmtfin_sf_\d", c): unit="sqft"
        elif c.endswith("_imputed") or c.endswith("_flag") or c in {"age_capped_zero","has_any_imputation","has_true_imputation","distance_available","price_iqr_outlier","area_iqr_outlier","unusual_area_gt4000"}: unit="0 hoặc 1"
        else: unit=count_units.get(c,"mã phân loại; xem bảng mã trong từ điển gốc")
        leakage = c in {"price", "sale_price", "price_per_sqft", "price_iqr_outlier"}
        if c in {"price", "sale_price"}: role="target hoặc target_alias"
        elif leakage: role="EDA_only; chứa giá mục tiêu, loại khỏi X dự báo"
        elif c in {"source_row_id","id","pid","order"}: role="identifier; không dùng làm biến liên tục"
        elif c in {"sale_type","sale_condition"}: role="transaction_metadata; cần kiểm tra thời điểm sẵn có khi dự báo"
        elif c.endswith("_imputed") or c in {"has_any_imputation","has_true_imputation","age_capped_zero","distance_available","area_iqr_outlier","unusual_area_gt4000","zero_room_flag"}: role="quality_flag; xem mục đích sử dụng"
        else: role="candidate_feature; xét thời điểm sẵn có và fit preprocessing trên train"
        field_events = [e for e in events if e["dataset"] == dataset and e["column"] == c]
        if c == "distance_to_center_km" and dataset == "ames":
            missing = "NA có chủ đích cho toàn bộ hàng vì nguồn không có tọa độ; không impute khoảng cách"
        elif field_events:
            missing = " | ".join(dict.fromkeys(e["rule"] for e in field_events))
        elif original:
            missing = "Không thiếu ở raw; giữ nguyên giá trị. " + ("Chỉ chuẩn hóa ngày sang ISO." if c == "date" else "Chuyển kiểu mã hoặc tên cột khi cần.")
        else:
            missing = "Biến suy ra từ các trường sạch; không có missing. Xem công thức hoặc mô tả biến."
        rows.append({"dataset": dataset,"column":c,"raw_column":names.get(c,"derived"),"dtype_clean":str(df[c].dtype),"unit":unit,"description_vi":meaning,"role":role,"target_leakage":int(leakage),"missing_policy":missing,"missing_after":int(df[c].isna().sum()),"n_unique":int(df[c].nunique(dropna=True)),"documentation":SOURCES['ames_documentation']['url'] if dataset == 'ames' else SOURCES['king_county']['origin']})
    return rows


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--refresh", action="store_true")
    options=args.parse_args()
    for p in ["data/raw", "data/processed", "metadata", "dictionaries", "docs"]:
        (ROOT/p).mkdir(parents=True, exist_ok=True)
    acquire(options.refresh)
    events=[]
    kr,k,ks=prepare_king()
    ar,a,ams=prepare_ames(events)
    summary={"king_county":ks,"ames":ams,"rules":{"outliers":"1.5IQR chỉ gắn cờ, giữ giá cao và diện tích lớn hợp lệ. King bedrooms>20 cách ly vì nghi nhập sai, không khẳng định đã xác minh.","missing":"NA cấu trúc dựa từ điển và counterpart; Unknown cho danh mục thiếu thực; trung vị neighborhood cho số thiếu thực. Giữ literal None của masonry.","age":"Tuổi tính tại năm bán, âm giữ raw_house_age và cờ, house_age đặt 0; không dùng năm hiện tại.","leakage":"price_per_sqft và mọi cờ chứa price chỉ cho EDA; khi modeling phải split trước rồi fit lại imputation/IQR/median/encoding trên train.","scope":"Hai thị trường và giai đoạn khác nhau, không ghép để suy diễn trực tiếp mức giá; sqft_living King bao gồm basement, Ames alias gr_liv_area chỉ trên mặt đất."}}
    dump_json(ROOT/"metadata/etl_summary.json",summary)
    pd.DataFrame(events,columns=["dataset","source_row_id","column","before","after","rule"]).to_csv(ROOT/"metadata/imputation_audit.csv",index=False)
    missing=[]
    for dataset,raw,df in [("king_county",kr,k),("ames",ar,a)]:
        for col in raw:
            clean=snake(col) if dataset=="ames" else col
            missing.append({"dataset":dataset,"raw_column":col,"clean_column":clean,"missing_before":int(raw[col].isna().sum()),"missing_after":int(df[clean].isna().sum()),"rows_before":len(raw),"rows_after":len(df)})
    pd.DataFrame(missing).to_csv(ROOT/"metadata/missingness_before_after.csv",index=False)
    audit=[]
    for dataset,df,identity in [("king_county",k,"id"),("ames",a,"pid")]:
        flags=[c for c in ["price_iqr_outlier","area_iqr_outlier","age_capped_zero","zero_room_flag","unusual_area_gt4000"] if c in df]
        flagged=df[flags].any(axis=1)
        for _,row in df.loc[flagged].iterrows():
            audit.append({"dataset":dataset,"source_row_id":int(row.source_row_id),"property_id":str(row[identity]),"price":row.price,"sqft_living":row.sqft_living,"raw_house_age":row.raw_house_age,"flags":";".join(c for c in flags if row[c]),"action":"retained_with_flags"})
    pd.DataFrame(audit).to_csv(ROOT/"metadata/outlier_audit.csv",index=False)
    dictionary=make_dictionary(kr,k,"king_county",events)+make_dictionary(ar,a,"ames",events)
    pd.DataFrame(dictionary).to_csv(ROOT/"dictionaries/data_dictionary.csv",index=False)
    log=f'''NHẬT KÝ ETL BỐN BƯỚC

1. EXTRACT THU THẬP
King County: {ks['raw_rows']:,} dòng, {ks['raw_columns']} biến; giai đoạn {ks['raw_date_min']} đến {ks['raw_date_max']}; lấy CSV mirror công khai, ghi cả nguồn Kaggle gốc.
Ames: {ams['raw_rows']:,} dòng, {ams['raw_columns']} biến; năm {ams['year_min']} đến {ams['year_max']}; lấy trực tiếp từ JSE, bài báo De Cock 2011.
Raw bất biến ở data/raw. metadata/sources.json lưu URL, thời điểm tải UTC, kích thước byte và SHA256; chạy lại kiểm checksum, --refresh mới tải lại.

2. TRANSFORM KIỂU DỮ LIỆU VÀ MISSING
King: ID và zipcode là chuỗi; ngày bán chuyển ISO YYYY-MM-DD. Không có missing.
Ames: chuẩn hóa tên snake_case, PID và MS SubClass là mã chuỗi. keep_default_na=False và na_values=['NA',''] tránh biến {ams['literal_None_preserved_mas_vnr_type']} giá trị masonry None hợp lệ thành missing.
Có {ams['original_missing_cells']:,} ô missing ban đầu. NA nghĩa không có tiện ích được điền nhãn cấu trúc theo từ điển; garage và basement đối chiếu diện tích/sức chứa trước khi kết luận không tồn tại. Thiếu thực danh mục là Unknown; số dùng trung vị neighborhood rồi fallback trung vị toàn bộ, không dùng giá bán. Năm gara sai miền được impute, không tự sửa 2207 thành 2007. Mỗi ô thay lưu before/after/rule và cờ _imputed.
Lưu {ams['imputation_or_structural_fill_cells']:,} lượt thay ô kể cả một năm gara sai; {ams['rows_with_any_fill']:,} hàng có ít nhất một ô thay. Trong đó {ams['true_imputation_cells']:,} ô ở {ams['rows_with_true_imputation']:,} hàng là missing thực hoặc năm gara sai miền; dùng has_true_imputation cho sensitivity thay vì loại toàn bộ hàng có NA cấu trúc. Không còn missing trong các trường gốc sau xử lý.

3. TRANSFORM NGOẠI LỆ VÀ TẠO BIẾN
Không loại đồng loạt giá đắt hoặc diện tích lớn. Gắn cờ 1.5IQR theo từng nguồn: King {ks['price_iqr_outliers']} giá và {ks['area_iqr_outliers']} diện tích; Ames {ams['price_iqr_outliers']} giá và {ams['area_iqr_outliers']} diện tích. Ames {ams['unusual_area_gt4000']} căn >4000sqft được giữ để sensitivity, theo cảnh báo của De Cock.
King cách ly {ks['quarantined_rows']} dòng gồm nghi số phòng ngủ >20 (dòng có 33 phòng); không có duplicate nguyên dòng. Giữ giao dịch lặp: {ks['unique_properties']:,} tài sản, {ks['repeat_transaction_rows_beyond_first']} giao dịch vượt lần đầu.
house_age=max(năm bán-năm xây,0). Có King {ks['age_capped_zero']} và Ames {ams['age_capped_zero']} tuổi âm; giữ raw_house_age và age_capped_zero để kiểm tra do nhà bán trước hoàn thiện hoặc ghi nhận năm chưa rõ.
price_per_sqft=price/sqft_living, USD/sqft. King sqft_living là sinh hoạt bên trong gồm basement; Ames dùng gr_liv_area trên mặt đất nên không so sánh trực tiếp đơn giá giữa hai nguồn.
Haversine dùng bán kính Trái Đất 6371.0088km đến điểm đại diện Seattle 47.6062,-122.3321 do nhóm quy ước; không phải định nghĩa địa lý chính thức của CBD hoặc khoảng cách đường đi. Ames thiếu lat/long và zipcode nên distance_to_center_km là NA có chủ đích, distance_available=0.

4. LOAD VÀ KIỂM TRA
Xuất king_county_clean.csv {ks['clean_rows']:,} dòng {ks['clean_columns']} cột, ames_clean.csv {ams['clean_rows']:,} dòng {ams['clean_columns']} cột, hai quarantine CSV, dictionary đầy đủ {len(dictionary)} dòng và các audit CSV.
Assertions: số dòng/cột raw đúng; giá và diện tích dương; tuổi sạch >=0; khoảng cách King trong 0..150km; ID Ames duy nhất; giữ resales King; không missing ngoài distance Ames; không tạo lat/long/zipcode Ames. Self-check Haversine cùng điểm bằng 0.
Phục vụ EDA toàn bộ mẫu sạch. Khi dự báo nhiệm vụ 4 phải chia train/test trước và fit lại imputation, ngưỡng IQR và encoding chỉ trên train; không dùng price_per_sqft, price_iqr_outlier hoặc nhãn giá thấp làm X. ID King cần split theo nhóm tài sản hoặc thời gian để tránh một nhà xuất hiện cả train và test.
'''
    (ROOT/"docs/nhat_ky_etl_4_buoc.txt").write_text(log,encoding="utf-8")
    assert abs(float(haversine(47.6062,-122.3321))) < 1e-9
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
