"""Quy tắc sàng lọc ứng viên "giá giao dịch thấp hơn dự báo, cần xác minh" (F05, F08).

Mục tiêu của quy tắc (do nhóm đặt, chưa được hiệu chỉnh bằng kết quả thẩm định thực tế):
ưu tiên căn có chênh lệch *tương đối* so với giá dự báo lớn, được cả ba mô hình cùng thấy,
và loại các trường hợp có khả năng cao là giao dịch đặc biệt/lỗi dữ liệu. Đây KHÔNG phải tối ưu
lợi nhuận hay phân bổ vốn; residual âm không chứng minh tài sản bị định giá thấp.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

BELOW_THRESHOLD = -0.20     # giá giao dịch thấp hơn giá dự báo ít nhất 20%
ANOMALY_CAP = -0.50         # thấp hơn quá 50% -> chuyển sang nhóm cần xác minh dữ liệu trước
N_CANDIDATES = 20           # ràng buộc ngân sách: Giám đốc đầu tư xét 20 căn

RULES = [
    ("R1", "Chỉ xét giao dịch gần nhất của mỗi tài sản", "Không chọn trùng một căn; giá mới nhất phản ánh tình trạng gần nhất"),
    ("R2", "Loại zero_room_flag = 1 (0 phòng ngủ hoặc 0 phòng tắm)", "Nghi lỗi nhập liệu"),
    ("R3", "Loại condition <= 2", "Giá thấp do hư hỏng là có lý do, không phải chênh lệch do mô hình bỏ sót"),
    ("R4", "Giá thấp hơn dự báo từ 20% đến 50% theo mô hình chính", "Dưới 50% thường là giao dịch không theo thị trường hoặc lỗi dữ liệu -> danh sách cần xác minh riêng"),
    ("R5", "Cả ba mô hình (LR, RF, XGBoost) cùng cho residual_pct <= -20%", "Giảm phụ thuộc một mô hình; ba mô hình dùng cùng dữ liệu nên KHÔNG phải ba bằng chứng độc lập"),
    ("R6", "Loại house_age = 0", "Bán khi đang/vừa xây, giá có thể là giá đất hoặc đặt cọc"),
    ("R7", "Xếp theo mức chênh lệch thận trọng (residual_pct ít âm nhất trong ba mô hình), lấy 20 căn đầu", "Mục tiêu: chênh lệch tương đối ổn định; không thiên vị nhà đắt như xếp theo USD"),
]

RESID_COLS = ("residual_pct", "residual_pct_rf", "residual_pct_lr")


def base_pool(val: pd.DataFrame) -> pd.DataFrame:
    """R1–R3."""
    return val[(val["is_latest_sale"] == 1) & (val["zero_room_flag"] == 0) & (val["condition"] >= 3)]


def recommended_mask(frame: pd.DataFrame, threshold=BELOW_THRESHOLD, cap=ANOMALY_CAP,
                     main="residual_pct", others=("residual_pct_rf", "residual_pct_lr")) -> pd.Series:
    """R4–R6."""
    cols = [main, *others]
    return ((frame[main] >= cap) & (frame[cols] <= threshold).all(axis=1) & (frame["house_age"] > 0))


def conservative_key(frame: pd.DataFrame, cols=RESID_COLS) -> pd.Series:
    return frame[list(cols)].max(axis=1)


def rank_candidates(frame: pd.DataFrame, n=N_CANDIDATES, key="residual_pct_conservative") -> pd.DataFrame:
    t = frame.sort_values([key, "id"]).head(n).copy()
    t.insert(0, "Hang", range(1, len(t) + 1))
    t["below_prediction_pct"] = (-100 * t["residual_pct"]).round(1)
    t["below_prediction_conservative_pct"] = (-100 * t["residual_pct_conservative"]).round(1)
    t["gap_to_prediction_usd"] = (t["predicted_price"] - t["price"]).round(0)
    assert t["id"].is_unique
    return t


def candidate_ids(resid: Mapping[str, pd.Series], pool_index, house_age: pd.Series, ids: pd.Series,
                  rank="conservative", n=N_CANDIDATES) -> list:
    """Chạy lại R4–R7 với một bộ residual khác (để đo độ ổn định danh sách).
    ``resid`` gồm khóa "m" (mô hình chính), "o1", "o2" (hai mô hình còn lại)."""
    r = pd.DataFrame({k: pd.Series(v) for k, v in resid.items()}).loc[pool_index]
    r["house_age"] = house_age.loc[pool_index]
    ok = recommended_mask(r, main="m", others=("o1", "o2"))
    key = r[["m", "o1", "o2"]].max(axis=1) if rank == "conservative" else r["m"]
    chosen = key[ok].sort_values(kind="mergesort").head(n).index
    return list(ids.loc[chosen])


def membership_frequency(variant_lists: Mapping[str, list], top_ids: list) -> pd.DataFrame:
    """Tần suất mỗi tài sản xuất hiện qua các biến thể -> cơ sở để nói về 'nhóm lõi'."""
    counts: dict = {}
    for ids in variant_lists.values():
        for i in ids:
            counts[i] = counts.get(i, 0) + 1
    n = len(variant_lists)
    out = pd.DataFrame({"id": list(counts), "So_lan_xuat_hien": list(counts.values())})
    out["Tong_so_bien_the"] = n
    out["Ty_le_xuat_hien_%"] = 100 * out["So_lan_xuat_hien"] / n
    out["Trong_danh_sach_chinh"] = out["id"].isin(top_ids).astype(int)
    out["Nhom_loi_moi_bien_the"] = (out["So_lan_xuat_hien"] == n).astype(int)
    return out.sort_values(["So_lan_xuat_hien", "Trong_danh_sach_chinh", "id"], ascending=[False, False, True])
