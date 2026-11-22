"""Kịch bản what-if giữ đúng quan hệ dữ liệu (F06) và đánh dấu kịch bản ra ngoài miền huấn luyện.

Kết quả what-if là *phản ứng của mô hình khi thay đầu vào*, không phải tác động nhân quả của
việc cải tạo/can thiệp ngoài thực tế (F07).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def check_area_invariant(d: pd.DataFrame) -> None:
    ok = np.isclose(d["sqft_living"], d["sqft_above"] + d["sqft_basement"])
    if not ok.all():
        raise AssertionError(f"Vi phạm sqft_living = sqft_above + sqft_basement ở {int((~ok).sum())} dòng")


def _recompute_living(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(sqft_living=d["sqft_above"] + d["sqft_basement"])


def above_ground_plus(pct: float) -> Callable[[pd.DataFrame], pd.DataFrame]:
    """Tăng diện tích trên mặt đất; tầng hầm giữ nguyên; tính lại tổng diện tích ở."""
    return lambda d: _recompute_living(d.assign(sqft_above=d["sqft_above"] * (1 + pct)))


def total_living_plus(pct: float) -> Callable[[pd.DataFrame], pd.DataFrame]:
    """Tăng cả trên mặt đất và tầng hầm cùng tỷ lệ (tổng diện tích ở tăng đúng pct)."""
    return lambda d: _recompute_living(d.assign(sqft_above=d["sqft_above"] * (1 + pct),
                                               sqft_basement=d["sqft_basement"] * (1 + pct)))


SCENARIOS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "Diện tích trên mặt đất +10% (hầm giữ nguyên)": above_ground_plus(0.10),
    "Tổng diện tích ở +10% (trên mặt đất và hầm cùng tỷ lệ)": total_living_plus(0.10),
    "Grade (chất lượng xây) +1": lambda d: d.assign(grade=(d["grade"] + 1).clip(upper=13)),
    "Condition (tình trạng) +1": lambda d: d.assign(condition=(d["condition"] + 1).clip(upper=5)),
    "View +1 bậc": lambda d: d.assign(view=(d["view"] + 1).clip(upper=4)),
    "Thêm 1 phòng tắm (cùng diện tích)": lambda d: d.assign(bathrooms=d["bathrooms"] + 1),
    "Thêm 1 phòng ngủ (cùng diện tích)": lambda d: d.assign(bedrooms=d["bedrooms"] + 1),
    "Tuổi nhà +10 năm": lambda d: d.assign(house_age=d["house_age"] + 10,
                                         years_since_update=d["years_since_update"] + 10),
    "Đặt về trạng thái vừa cải tạo (years_since_update = 0)": lambda d: d.assign(is_renovated=1, years_since_update=0),
    "Thời điểm bán +6 tháng": lambda d: d.assign(month_index=d["month_index"] + 6),
    "Diện tích đất +20%": lambda d: d.assign(sqft_lot=d["sqft_lot"] * 1.2),
}

DOMAIN_COLS = ["sqft_living", "sqft_above", "sqft_basement", "sqft_lot", "grade", "condition", "view",
               "bathrooms", "bedrooms", "house_age", "years_since_update", "month_index"]


def apply_scenario(name: str, X: pd.DataFrame) -> pd.DataFrame:
    out = SCENARIOS[name](X.copy())
    check_area_invariant(out)
    return out


def out_of_domain_share(X_new: pd.DataFrame, X_train: pd.DataFrame) -> float:
    """Tỷ lệ dòng có ít nhất một biến vượt min/max quan sát được trong dữ liệu huấn luyện."""
    lo, hi = X_train[DOMAIN_COLS].min(), X_train[DOMAIN_COLS].max()
    outside = ((X_new[DOMAIN_COLS] < lo) | (X_new[DOMAIN_COLS] > hi)).any(axis=1)
    return float(outside.mean())


def run_whatif(model, X_eval: pd.DataFrame, X_train: pd.DataFrame) -> pd.DataFrame:
    base = model.predict(X_eval)
    rows = []
    for name in SCENARIOS:
        Xs = apply_scenario(name, X_eval)
        changed = (Xs[DOMAIN_COLS] != X_eval[DOMAIN_COLS]).any(axis=1)
        chg = model.predict(Xs) / base - 1
        rows.append({"Kich_ban": name, "Trung_vi_thay_doi_%": 100 * np.median(chg),
                     "Trung_binh_thay_doi_%": 100 * chg.mean(),
                     "P10_%": 100 * np.percentile(chg, 10), "P90_%": 100 * np.percentile(chg, 90),
                     "Ty_le_dong_bi_thay_doi_%": 100 * changed.mean(),
                     "Ty_le_ngoai_mien_huan_luyen_%": 100 * out_of_domain_share(Xs, X_train)})
    return pd.DataFrame(rows).sort_values("Trung_vi_thay_doi_%", ascending=False)
