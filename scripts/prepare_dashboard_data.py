"""Nhiệm vụ 5: dựng bảng dữ liệu cho dashboard Power BI.

Đọc output nhiệm vụ 4 (OOF predictions, top 20, metrics, sensitivity),
tính thêm OOF cho Ames (cùng pipeline Nhiệm vụ 4, điền thiếu học trong từng fold — F01), xuất CSV vào dashboard/data.

Tên cột CSV giữ như bản Power BI đầu tiên (upside_usd, discount_pct, undervalued_20pct, models_agree_undervalued)
để semantic model không đổi schema; ý nghĩa: upside_usd = chênh lệch so với giá dự báo (không phải lợi nhuận),
discount_pct = % giá giao dịch thấp hơn giá dự báo, undervalued_20pct = thấp hơn dự báo ≥ 20% (ứng viên cần xác minh).

Chạy: python scripts/prepare_dashboard_data.py
"""
from pathlib import Path
import json

import sys

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bds_valuation import ames as A  # noqa: E402
from bds_valuation import selection as S  # noqa: E402
T4 = ROOT / "outputs" / "task4" / "tables"
T5 = ROOT / "outputs" / "task5" / "tables"
OUT = ROOT / "dashboard" / "data"
for p in (T5, OUT):
    p.mkdir(parents=True, exist_ok=True)

SEED = 42
THRESHOLD = 0.20
PRICE_BINS = [0, 250_000, 400_000, 550_000, 750_000, 1_000_000, np.inf]
PRICE_LABELS = ["<250k", "250-400k", "400-550k", "550-750k", "750k-1M", ">=1M"]


def band(prices):
    return pd.cut(prices, bins=PRICE_BINS, labels=PRICE_LABELS, right=False)


def save(df, name):
    df.to_csv(OUT / name, index=False, date_format="%Y-%m-%d", encoding="utf-8")
    print(f"  {name}: {len(df):,} dòng x {len(df.columns)} cột")


# ---------------------------------------------------------------- King County
king = pd.read_csv(T4 / "king_oof_predictions.csv", dtype={"id": "string", "zipcode": "string"})
king["date"] = pd.to_datetime(king["date"])
king["sale_year"] = king["date"].dt.year
king["sale_month"] = king["date"].dt.to_period("M").astype(str)
king["price_band"] = band(king["price"])
king["discount_pct"] = (-100 * king["residual_pct"]).round(2)
king["discount_conservative_pct"] = (-100 * king["residual_pct_conservative"]).round(2)
king["upside_usd"] = (king["predicted_price"] - king["price"]).round(0)
king["is_latest_sale"] = king["is_latest_sale"].astype(int)
king["undervalued_20pct"] = king["below_prediction_20pct"].astype(int)
king["models_agree_undervalued"] = king["models_agree_below_20pct"].astype(int)
king = king.drop(columns=["below_prediction_20pct", "models_agree_below_20pct", "residual_pct_nested"])
zip_top = king["zipcode"].value_counts().head(12).index
king["zip_top"] = king["zipcode"].where(king["zipcode"].isin(zip_top), "Khac")

save(king, "fact_king.csv")

# ---------------------------------------------------------------- Ames OOF
ames_raw = pd.read_csv(ROOT / "data/processed/ames_clean.csv", keep_default_na=False,
                       na_values=[""], dtype={"pid": "string", "ms_subclass": "string"})
ames, _ = A.load_ames_for_modeling(ROOT / "data/processed/ames_clean.csv", ROOT / "metadata/imputation_audit.csv")
feats, num, cat = A.ames_feature_lists(ames)
X, y, groups = ames[feats], ames["price"], ames["pid"]

oof = np.zeros(len(X))
for train_idx, test_idx in GroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y, groups):
    model = A.make_ames_model("xgb", num, cat, seed=SEED)     # điền thiếu học trên train của fold
    oof[test_idx] = model.fit(X.iloc[train_idx], y.iloc[train_idx]).predict(X.iloc[test_idx])
ames = ames_raw            # bảng hiển thị dùng giá trị đã làm sạch của Nhiệm vụ 2

ames_out = ames[["pid", "neighborhood", "price", "gr_liv_area", "overall_qual", "year_built",
                 "house_age", "bedroom_abvgr", "garage_cars", "lot_area", "yr_sold"]].copy()
ames_out["bathrooms_total"] = (ames["full_bath"] + 0.5 * ames["half_bath"]
                               + ames["bsmt_full_bath"] + 0.5 * ames["bsmt_half_bath"])
ames_out["predicted_price"] = oof.round(0)
ames_out["residual_pct"] = ames_out["price"] / ames_out["predicted_price"] - 1
ames_out["discount_pct"] = (-100 * ames_out["residual_pct"]).round(2)
ames_out["upside_usd"] = (ames_out["predicted_price"] - ames_out["price"]).round(0)
ames_out["price_band"] = band(ames_out["price"])
ames_out["is_undervalued_20pct"] = (ames_out["residual_pct"] <= -THRESHOLD).astype(int)
nb_top = ames_out["neighborhood"].value_counts().head(12).index
ames_out["neighborhood_top"] = ames_out["neighborhood"].where(
    ames_out["neighborhood"].isin(nb_top), "Khac")
ames_out.to_csv(T5 / "ames_oof_predictions.csv", index=False, encoding="utf-8")
save(ames_out, "fact_ames.csv")

# ---------------------------------------------------------------- Bảng phụ
top20 = pd.read_csv(T4 / "top20_candidates_below_prediction_king.csv", dtype={"id": "string", "zipcode": "string"})
top20 = top20.rename(columns={
    "gap_to_prediction_usd": "upside_usd", "below_prediction_pct": "discount_pct",
    "below_prediction_conservative_pct": "discount_conservative_pct",
    "models_agree_below_20pct": "models_agree_undervalued", "cumulative_price_usd": "cumulative_cost_usd"})
top20["price_band"] = band(top20["price"])
save(top20, "top20.csv")

metrics = pd.read_csv(T4 / "model_metrics_mape_report.csv")
metrics = metrics.rename(columns={
    "Thi_truong": "market", "Mo_hinh": "model", "MAPE_%": "mape", "MdAPE_%": "mdape",
    "RMSE": "rmse", "MAE": "mae", "R2": "r2", "Ty_le_sai_<=10%": "acc10",
    "Ty_le_sai_<=20%": "acc20", "Thoi_gian_fit_s": "fit_seconds"})
save(metrics[["market", "model", "mape", "mdape", "rmse", "mae", "r2", "acc10", "acc20"]],
     "model_metrics.csv")

seg = pd.read_csv(T4 / "mape_by_price_segment.csv").rename(columns={
    "Mo_hinh": "model", "Phan_khuc": "segment", "So_giao_dich": "n",
    "Khoang_gia_USD": "price_range", "MAPE_%": "mape"})
save(seg, "mape_by_segment.csv")

# Bảng so sánh rộng cho biểu đồ cột nhóm (Power BI không cần Series phức tạp)
def short_model(name):
    if name.startswith("Linear"):
        return "Linear Regression"
    if name.startswith("Random"):
        return "Random Forest"
    if name.startswith("XGBoost"):
        return "XGBoost"
    return "Naive"


def market_of(name):
    if name.startswith("Ames"):
        return "ames"
    if "thời gian" in name:
        return "time"
    if "nested" in name:
        return "nested"
    return "king"


m = metrics[["market", "model", "mape", "rmse", "r2"]].copy()
m["model"] = m["model"].map(short_model)
m["scope"] = m["market"].map(market_of)
compare = m.pivot_table(index="model", columns="scope",
                        values=["mape", "rmse", "r2"], aggfunc="max")
compare.columns = [f"{a}_{b}" for a, b in compare.columns]
compare = compare.reset_index()
compare = compare[compare["model"] != "Naive"].round(4)
save(compare, "model_compare.csv")

long = compare.melt(id_vars="model",
                    value_vars=["mape_king", "mape_ames"],
                    var_name="market", value_name="mape")
long["market"] = long["market"].map({"mape_king": "King", "mape_ames": "Ames"})
long = long.dropna(subset=["mape"]).round(3)
save(long, "model_compare_long.csv")

seg_c = seg[seg["model"].str.startswith(("Linear", "XGBoost"))].copy()
seg_c["model"] = seg_c["model"].map(short_model)
seg_wide = seg_c.pivot_table(index="segment", columns="model", values="mape", aggfunc="max").reset_index()
seg_wide.columns = ["segment", "mape_lr", "mape_xgb"]
seg_wide["order"] = seg_wide["segment"].str.extract(r"Q(\d)").astype(int)
seg_wide = seg_wide.sort_values("order").drop(columns="order").round(3)
save(seg_wide, "segment_compare.csv")

sens = pd.read_csv(T4 / "sensitivity_threshold.csv").rename(columns={
    "Nguong_%": "threshold_pct", "So_can_ung_vien": "candidates",
    "Ty_le_ung_vien_%": "share_pct", "Ca_3_mo_hinh_dong_y": "all3",
    "Trong_do_thap_hon_qua_50%": "over_50pct", "Gia_trung_vi_USD": "median_price",
    "Du_20_can": "enough_20"})
save(sens, "sensitivity.csv")

perm = pd.read_csv(T4 / "permutation_importance.csv").rename(columns={
    "Bien": "feature", "MAPE_tang_diem_%": "mape_increase_pp", "Do_lech_chuan": "std_pp"})
save(perm, "importance.csv")
save(perm.head(12).copy(), "importance_top.csv")

stab = pd.read_csv(T4 / "sensitivity_top20_stability.csv").rename(columns={
    "Bien_the": "variant", "Trung_voi_ds_chinh": "overlap_20", "Ty_le_%": "share_pct"})
save(stab, "stability.csv")

whatif = pd.read_csv(T4 / "sensitivity_whatif.csv").rename(columns={
    "Kich_ban": "scenario", "Trung_vi_thay_doi_%": "median_change_pct",
    "Trung_binh_thay_doi_%": "mean_change_pct", "P10_%": "p10", "P90_%": "p90"})
save(whatif, "whatif_scenarios.csv")

# ---------------------------------------------------------------- Kiểm tra
summary = json.loads((T4 / "task4_summary.json").read_text(encoding="utf-8"))
pool = king[(king.is_latest_sale == 1) & (king.zero_room_flag == 0) & (king.condition >= 3)]
assert len(king) == 21612, len(king)
assert len(ames_out) == 2930, len(ames_out)
n20 = int((pool.residual_pct <= -THRESHOLD).sum())
assert sens.loc[sens.threshold_pct == 20, "candidates"].item() == n20
assert len(pool) == summary["candidate_pool_size"]
assert list(top20["id"]) == list(pd.read_csv(T4 / "top20_candidates_below_prediction_king.csv", dtype={"id": "string"})["id"])
ames_mape = 100 * mean_absolute_percentage_error(y, oof)
print(f"King: {len(king):,} | pool {len(pool):,} | Ames OOF MAPE {ames_mape:.2f}% "
      f"| Ames undervalued@20%: {ames_out.is_undervalued_20pct.sum():,}")

meta = {
    "source": "outputs/task4/tables + ames_clean.csv",
    "king_rows": len(king), "ames_rows": len(ames_out),
    "king_pool_rows": len(pool),
    "ames_oof_mape_pct": round(float(ames_mape), 3),
    "ames_undervalued_20pct": int(ames_out.is_undervalued_20pct.sum()),
    "threshold_pct": 20,
    "king_candidates_20pct": n20,
    "king_share_20pct": round(100 * n20 / len(pool), 2),
    "definition": "residual_pct = price / predicted_price - 1 (OOF); ứng viên cần xác minh khi residual_pct <= -nguong "
                  "(giá giao dịch thấp hơn dự báo; chưa chứng minh bị định giá thấp)",
    "king_scope": "is_latest_sale=1, zero_room_flag=0, condition>=3 (giống nhiệm vụ 4)",
    "ames_scope": "toàn bộ 2.930 tài sản; chỉ kiểm chứng, không dùng chọn 20 căn",
}
(T5 / "dashboard_data_summary.json").write_text(
    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print("Xong:", OUT)
