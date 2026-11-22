# %% [markdown]
# # Nhiệm vụ 4 — Mô hình dự báo giá & 20 ứng viên có giá giao dịch thấp hơn dự báo
# Chủ đề 14: Mô hình định giá bất động sản tự động. **Phiên bản 2** (sửa theo feedback 21/11/2026, mã F01–F12).
#
# **Đầu vào:** dữ liệu sạch của Nhiệm vụ 2 (`data/processed/*.csv`).
# **Đầu ra:** `models/model.pkl`, `outputs/task4/tables/*`, `outputs/task4/figures/*`.
#
# Logic dùng lại (tạo biến, registry mô hình, đánh giá, what-if, quy tắc chọn, dự báo) nằm trong package
# `bds_valuation/`; import package không huấn luyện gì. Script này là luồng chạy đầy đủ và cũng là nguồn của
# notebook `notebooks/04_Modeling.ipynb`.
#
# Quy trình:
# 1. Đọc dữ liệu, tạo biến qua `engineer_king_features` (cùng hàm dùng khi dự báo); loại biến rò rỉ giá.
# 2. Chia train/test 80/20 **theo id tài sản**. Tập test là tập đánh giá cuối, không dùng để chọn gì.
# 3. Tinh chỉnh XGBoost và **chọn mô hình bằng CV trên train** (F04: mọi bước dùng chung một registry).
# 4. Đánh giá test; MAPE theo phân khúc; **backtest thời gian độc lập** (F02); **nested CV** (F03).
# 5. OOF cho sàng lọc → residual → 20 ứng viên *giá giao dịch thấp hơn dự báo, cần xác minh* (F05, F08).
# 6. Độ nhạy: what-if giữ quan hệ diện tích (F06), permutation importance, ngưỡng %, tần suất xuất hiện top 20.
# 7. Kiểm chứng phụ trên Ames với điền thiếu học trong Pipeline (F01).

# %%
import json
import os
import sys
import time
import warnings
from pathlib import Path


def _locate_root():
    """Script: đi lên từ __file__. Notebook: đi lên từ cwd. Hoặc đặt BDS_PROJECT_ROOT (F11)."""
    if os.environ.get("BDS_PROJECT_ROOT"):
        return Path(os.environ["BDS_PROJECT_ROOT"]).expanduser().resolve()
    try:
        start = Path(__file__).resolve().parent
    except NameError:                      # notebook không có __file__
        start = Path.cwd().resolve()
    for cand in (start, *start.parents):
        if (cand / "bds_valuation").is_dir() and (cand / "data" / "processed").is_dir():
            return cand
    raise FileNotFoundError("Không tìm thấy thư mục gốc project; đặt BDS_PROJECT_ROOT.")


sys.path.insert(0, str(_locate_root()))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from bds_valuation import ames as A
from bds_valuation import selection as S
from bds_valuation.evaluation import (group_split, metrics, nested_cv_oof, oof_predict, run_temporal_backtest,
                                      select_by_cv, tune_xgb)
from bds_valuation.features import CAT_FEATURES, FEATURES, LEAKAGE, NUM_FEATURES, load_king_clean
from bds_valuation.models import (LR_NAME, MODEL_NAMES, RF_NAME, SEED, XGB_NAME, build_model,
                                  check_bundle_consistency)
from bds_valuation.paths import find_project_root, project_paths
from bds_valuation.whatif import run_whatif

warnings.filterwarnings("ignore", category=UserWarning)

P = project_paths(find_project_root(_locate_root()))
ROOT, DATA, OUT_T, OUT_F, OUT_M = P["root"], P["data"], P["tables"], P["figures"], P["models"]
FAST = os.environ.get("BDS_FAST") == "1"     # chạy nhanh để kiểm tra luồng (ít vòng tinh chỉnh); kết quả nộp dùng FAST=0
N_ITER, N_ITER_NESTED = (3, 2) if FAST else (20, 10)

# Bảng màu (đã kiểm định cho người mù màu) — xanh = mô hình chính, cam = nổi bật/ứng viên
BLUE, ORANGE, AQUA, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#a3a29c", "#0b0b0b", "#52514e"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "axes.edgecolor": "#d6d5cf", "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.titlecolor": INK, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#ecebe7", "grid.linewidth": 0.8, "font.size": 10, "figure.dpi": 110,
})


def savefig(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT_F / f"{name}.{ext}", bbox_inches="tight", dpi=160 if ext == "png" else None)
    plt.close(fig)


print("ROOT =", ROOT)
print("python", sys.version.split()[0], "| pandas", pd.__version__, "| sklearn", sklearn.__version__,
      "| xgboost", xgboost.__version__, "| FAST =", FAST)

# %% [markdown]
# ## 1. Đọc dữ liệu King County và tạo biến
# `load_king_clean` đọc đúng kiểu theo `docs/data_handoff.txt` rồi gọi `engineer_king_features` — **cùng một hàm**
# mà `bds_valuation.predict` dùng khi dự báo căn mới (F12). Biến thêm (chỉ dùng thông tin có trước giao dịch):
# `is_renovated`, `years_since_update` = năm bán − max(năm xây, năm cải tạo), `month_index` = số tháng kể từ 05/2014.
# Loại khỏi X: `price` (mục tiêu), `price_per_sqft`, `price_iqr_outlier` (chứa giá), các mã truy vết.

# %%
king = load_king_clean(DATA / "king_county_clean.csv")
assert not LEAKAGE & set(FEATURES), "Biến rò rỉ giá nằm trong X!"
X, y, groups = king[FEATURES], king["price"], king["id"]
print(f"King County: {len(king):,} giao dịch, {king['id'].nunique():,} tài sản, {len(FEATURES)} biến đầu vào")

# %% [markdown]
# ## 2. Chia train/test theo id tài sản
# Tập test (20%) là **tập đánh giá cuối**: không tham gia tinh chỉnh, không tham gia chọn mô hình.

# %%
tr_idx, te_idx = group_split(X, y, groups, test_size=0.2, seed=SEED)
X_tr, X_te, y_tr, y_te = X.iloc[tr_idx], X.iloc[te_idx], y.iloc[tr_idx], y.iloc[te_idx]
g_tr = groups.iloc[tr_idx]
print(f"Train {len(X_tr):,} | Test {len(X_te):,} | id trùng giữa hai tập: {len(set(g_tr) & set(groups.iloc[te_idx]))}")

# %% [markdown]
# ## 3. Tinh chỉnh và chọn mô hình trên train
# Mọi mô hình học trên **log(price)** rồi đổi ngược về USD (`TransformedTargetRegressor`), tiền xử lý nằm trong Pipeline.
# Ba mô hình lấy từ **một registry** (`bds_valuation.models.MODEL_REGISTRY`) — cùng ánh xạ cho đánh giá, OOF và
# final fit, nên mô hình nào thắng (kể cả Linear Regression) thì đúng mô hình đó được lưu (F04).
#
# ### 3a. Mốc so sánh thô: trung vị đơn giá theo zipcode × diện tích (cách "định giá thủ công")

# %%
ppsf_tr = (y_tr / X_tr["sqft_living"]).groupby(X_tr["zipcode"]).median()
naive_pred = X_te["zipcode"].map(ppsf_tr).fillna((y_tr / X_tr["sqft_living"]).median()) * X_te["sqft_living"]

# %% [markdown]
# ### 3b. Tinh chỉnh XGBoost (RandomizedSearch, GroupKFold 3 theo id, chỉ trên train)

# %%
t0 = time.time()
inner_tr = list(GroupKFold(n_splits=3, shuffle=True, random_state=SEED).split(X_tr, y_tr, g_tr))
BEST_XGB, search = tune_xgb(X_tr, y_tr, cv=inner_tr, n_iter=N_ITER, seed=SEED)
TUNED = {XGB_NAME: BEST_XGB}
print(f"Tinh chỉnh xong sau {time.time()-t0:.0f}s — CV MAPE tốt nhất = {-100*search.best_score_:.2f}%")
print("Tham số tốt nhất:", BEST_XGB)
pd.DataFrame(search.cv_results_).sort_values("rank_test_score")[
    ["rank_test_score", "mean_test_score", "std_test_score", "params"]
].assign(mean_test_MAPE_pct=lambda d: -100 * d["mean_test_score"]).to_csv(OUT_T / "xgb_tuning_results.csv", index=False)

# %% [markdown]
# ### 3c. Chọn mô hình bằng CV trên train (không nhìn tập test)
# Dùng lại 3 fold theo id ở trên. Điểm CV của XGBoost hơi lạc quan vì chính các fold này đã dùng để tinh chỉnh;
# nested CV ở mục 3g đo cả bước tinh chỉnh + chọn mô hình một cách nghiêm ngặt.

# %%
BEST_NAME, cv_scores = select_by_cv(X_tr, y_tr, inner_tr, TUNED, seed=SEED)
cv_table = pd.DataFrame({"Mo_hinh": list(cv_scores), "CV_MAPE_train_%": list(cv_scores.values())})
cv_table["Duoc_chon"] = cv_table["Mo_hinh"].eq(BEST_NAME)
cv_table.to_csv(OUT_T / "model_selection_cv_train.csv", index=False)
print(cv_table.round(3).to_string(index=False))
print("\nMô hình được chọn (trước khi xem test):", BEST_NAME)

# %% [markdown]
# ### 3d. Đánh giá cuối trên tập test

# %%
models, preds, fit_time = {}, {"Mốc thô: đơn giá zipcode × diện tích": naive_pred.values}, {}
for name in MODEL_NAMES:
    t0 = time.time()
    models[name] = build_model(name, seed=SEED, params=TUNED.get(name)).fit(X_tr, y_tr)
    fit_time[name] = time.time() - t0
    preds[name] = models[name].predict(X_te)
metrics_king = pd.DataFrame([{"Thi_truong": "King County", "Mo_hinh": n, **metrics(y_te, p),
                              "Thoi_gian_fit_s": fit_time.get(n, 0.0),
                              "Chon_bang_CV_train": n == BEST_NAME} for n, p in preds.items()])
print(metrics_king.drop(columns=["Thi_truong"]).round(3).to_string(index=False))
best_model = models[BEST_NAME]
test_best = metrics_king.set_index("Mo_hinh")["MAPE_%"].drop("Mốc thô: đơn giá zipcode × diện tích").idxmin()
print(f"\nMô hình chọn bằng CV: {BEST_NAME} | mô hình có MAPE test thấp nhất: {test_best} "
      f"({'trùng' if test_best == BEST_NAME else 'KHÁC — báo cáo theo mô hình đã chọn trước'})")

# %% [markdown]
# ### 3e. MAPE theo phân khúc giá

# %%
seg = pd.qcut(y_te, 5, labels=["Q1 rẻ nhất", "Q2", "Q3", "Q4", "Q5 đắt nhất"])
seg_rows = []
for name in dict.fromkeys([LR_NAME, BEST_NAME]):
    ape = np.abs(preds[name] - y_te.values) / y_te.values
    for s in seg.cat.categories:
        msk = (seg == s).values
        seg_rows.append({"Mo_hinh": name, "Phan_khuc": s, "So_giao_dich": int(msk.sum()),
                         "Khoang_gia_USD": f"{y_te[msk].min():,.0f} – {y_te[msk].max():,.0f}",
                         "MAPE_%": 100 * ape[msk].mean()})
mape_segment = pd.DataFrame(seg_rows)
mape_segment.to_csv(OUT_T / "mape_by_price_segment.csv", index=False)
print(mape_segment.round(2).to_string(index=False))

# %% [markdown]
# ### 3f. Backtest theo thời gian độc lập (F02)
# Tách **tương lai trước** (giao dịch từ 01/02/2015, chỉ tài sản chưa xuất hiện trong quá khứ). Trong quá khứ:
# fit khi tinh chỉnh = giao dịch trước 01/11/2014, validation = 3 tháng cuối quá khứ. Tinh chỉnh XGBoost và chọn
# mô hình chỉ trên quá khứ, **khóa cấu hình**, fit lại trên toàn bộ quá khứ rồi chấm tương lai đúng một lần.

# %%
t0 = time.time()
metrics_time, temporal_info = run_temporal_backtest(X, y, king["date"], groups, cutoff="2015-02-01",
                                                    n_iter=N_ITER, seed=SEED)
(OUT_T / "temporal_backtest.json").write_text(json.dumps(temporal_info, ensure_ascii=False, indent=2, default=float),
                                              encoding="utf-8")
print(json.dumps({k: temporal_info[k] for k in ("cutoff", "validation_start", "past_rows", "inner_train_rows",
                                                 "inner_validation_rows", "future_rows", "locked_model")},
                 ensure_ascii=False, default=float))
print(metrics_time[["Mo_hinh", "MAPE_%", "RMSE", "R2", "Chon_truoc_khi_xem_tuong_lai"]].round(3).to_string(index=False))
print(f"({time.time()-t0:.0f}s)")

# %% [markdown]
# ### 3g. Nested CV — ước lượng hiệu năng nghiêm ngặt (F03)
# Outer: GroupKFold 5 theo id trên toàn bộ giao dịch. Trong **mỗi outer-train**: tinh chỉnh XGBoost
# (GroupKFold 3 theo id) và chọn giữa LR/RF/XGBoost; sau đó mới dự báo outer-test. Không tài sản nào của
# outer-test tham gia fit, tinh chỉnh hay chọn mô hình cho chính nó.

# %%
t0 = time.time()
oof_nested, nested_folds = nested_cv_oof(X, y, groups, outer_splits=5, inner_splits=3, n_iter=N_ITER_NESTED, seed=SEED)
nested_folds.to_csv(OUT_T / "nested_cv_folds.csv", index=False)
nested_metrics = {"Thi_truong": "King County (nested CV 5×3, OOF)", "Mo_hinh": "Quy trình: tinh chỉnh + chọn mô hình trong từng fold",
                  **metrics(y, oof_nested), "Thoi_gian_fit_s": time.time() - t0}
print(f"Nested CV MAPE = {nested_metrics['MAPE_%']:.2f}% ({time.time()-t0:.0f}s)")

# %% [markdown]
# ### 3h. Biểu đồ: so sánh mô hình, thực tế vs dự báo

# %%
fig, ax = plt.subplots(figsize=(7.5, 3.4))
mk = metrics_king.sort_values("MAPE_%", ascending=True)
colors = [BLUE if n == BEST_NAME else GRAY for n in mk["Mo_hinh"]]
bars = ax.barh(mk["Mo_hinh"], mk["MAPE_%"], color=colors, height=0.55)
ax.invert_yaxis()
for b, v in zip(bars, mk["MAPE_%"]):
    ax.text(v + 0.3, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", color=INK, fontsize=10)
ax.set_xlabel("MAPE trên tập test (%) — càng thấp càng tốt")
ax.set_title("King County: MAPE theo mô hình (xanh = mô hình chọn bằng CV trên train)", loc="left")
ax.grid(axis="y", visible=False)
savefig(fig, "king_model_comparison_mape")

fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharex=True, sharey=True)
for ax, name in zip(axes, [LR_NAME, BEST_NAME]):
    p = preds[name]
    ax.scatter(y_te / 1e6, p / 1e6, s=6, alpha=0.35, color=BLUE, linewidths=0)
    lim = [0.05, 5]
    ax.plot(lim, lim, color=INK, lw=1, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ticks = [0.1, 0.2, 0.5, 1, 2, 5]
    ax.set_xticks(ticks, [str(t) for t in ticks]); ax.set_yticks(ticks, [str(t) for t in ticks])
    ax.minorticks_off()
    ax.set_title(f"{name} — MAPE {100*mean_absolute_percentage_error(y_te, p):.1f}%", loc="left", fontsize=11)
    ax.set_xlabel("Giá thực tế (triệu USD, thang log)")
axes[0].set_ylabel("Giá dự báo (triệu USD, thang log)")
fig.suptitle("Thực tế và dự báo trên tập test — điểm càng sát đường chéo càng đúng", x=0.06, y=1.02,
             ha="left", fontweight="bold", color=INK)
savefig(fig, "king_actual_vs_predicted")

# %% [markdown]
# ## 4. Residual out-of-fold cho sàng lọc
# Mỗi giao dịch được dự báo bởi mô hình **chưa fit trên tài sản đó** (GroupKFold 5 theo id).
# **Giới hạn (F03):** cấu hình XGBoost ở đây là bộ tham số đã chọn ở mục 3b từ train, nên một số tài sản được dự
# báo OOF đã gián tiếp tham gia chọn siêu tham số. "Chưa thấy tài sản" chỉ đúng ở bước fit. OOF này dùng để **sàng
# lọc**; ước lượng hiệu năng nghiêm ngặt là nested CV ở mục 3g.
#
# `residual = giá giao dịch − giá dự báo`; `residual_pct = giá giao dịch / giá dự báo − 1`.
# residual_pct ≤ −20% nghĩa là **giá giao dịch thấp hơn dự báo ít nhất 20%** — chưa chứng minh bị định giá thấp:
# chênh lệch có thể do mô hình dự báo cao, thiếu đặc điểm quan trọng, giao dịch đặc biệt, lỗi dữ liệu, hoặc cơ hội thật.

# %%
SEEDS = [42, 1, 7, 2024]
t0 = time.time()
oof = {n: oof_predict(n, X, y, groups, seed=SEED, params=TUNED.get(n)) for n in MODEL_NAMES}
oof_seeds = {SEED: oof[BEST_NAME]}
oof_seeds.update({s: oof_predict(BEST_NAME, X, y, groups, seed=s, params=TUNED.get(BEST_NAME))
                  for s in SEEDS if s != SEED})
oof_best = np.mean([oof_seeds[s] for s in SEEDS], axis=0)       # mô hình chính: TB 4 seed chia fold
others = [n for n in MODEL_NAMES if n != BEST_NAME]
print(f"OOF xong sau {time.time()-t0:.0f}s")
print(f"OOF MAPE — {BEST_NAME} (TB 4 seed): {100*mean_absolute_percentage_error(y, oof_best):.2f}% | " +
      " | ".join(f"{n}: {100*mean_absolute_percentage_error(y, oof[n]):.2f}%" for n in others) +
      f" | nested CV: {nested_metrics['MAPE_%']:.2f}%")

val = king[["source_row_id", "id", "date", "price", "zipcode", "lat", "long", "bedrooms", "bathrooms",
            "sqft_living", "sqft_lot", "grade", "condition", "view", "waterfront", "house_age",
            "is_renovated", "distance_to_center_km", "zero_room_flag"]].copy()
val["predicted_price"] = oof_best.round(0)
val["residual"] = (val["price"] - val["predicted_price"]).round(0)
val["residual_pct"] = val["price"] / val["predicted_price"] - 1
SHORT = {LR_NAME: "lr", RF_NAME: "rf", XGB_NAME: "xgb"}
OTHER_COL = {n: f"residual_pct_{SHORT[n]}" for n in others}     # mô hình chính XGBoost -> residual_pct_lr, residual_pct_rf
for n, c in OTHER_COL.items():
    val[c] = val["price"] / oof[n] - 1
RCOLS = ["residual_pct", *OTHER_COL.values()]
val["residual_pct_nested"] = val["price"] / oof_nested - 1
val["residual_pct_conservative"] = val[RCOLS].max(axis=1)     # căn chỉ xếp cao khi cả 3 mô hình cùng thấy thấp
val["below_prediction_20pct"] = (val["residual_pct"] <= S.BELOW_THRESHOLD).astype(int)
val["models_agree_below_20pct"] = (val[RCOLS] <= S.BELOW_THRESHOLD).sum(axis=1)
val["is_latest_sale"] = (val["date"] == val.groupby("id")["date"].transform("max")).astype(int)
val.to_csv(OUT_T / "king_oof_predictions.csv", index=False, date_format="%Y-%m-%d")
print(f"Giao dịch có giá thấp hơn dự báo ≥20%: {100*val['below_prediction_20pct'].mean():.2f}% "
      f"({val['below_prediction_20pct'].sum():,} giao dịch)")

# %% [markdown]
# ## 5. Danh sách 20 ứng viên cần xác minh
# **Mục tiêu của quy tắc** (do nhóm đặt): ưu tiên chênh lệch *tương đối* so với giá dự báo, ổn định qua ba mô hình,
# loại trường hợp nhiều khả năng là giao dịch đặc biệt/lỗi dữ liệu. Ngưỡng −20%, trần −50%, lọc tuổi nhà là
# **quy tắc lựa chọn của nhóm, chưa được hiệu chỉnh bằng kết quả thẩm định thực tế**. Danh sách không phải tối ưu
# đầu tư; các giao dịch là lịch sử 2014–2015, không xác nhận hiện có thể mua ở giá đó.

# %%
rules = pd.DataFrame(S.RULES, columns=["Ma", "Quy_tac", "Ly_do"])
rules.to_csv(OUT_T / "selection_rules.csv", index=False)
print(rules[["Ma", "Quy_tac"]].to_string(index=False))

pool = S.base_pool(val)
others_cols = tuple(OTHER_COL.values())
pool_rec = pool[S.recommended_mask(pool, others=others_cols)]
top20 = S.rank_candidates(pool_rec)
top20["cumulative_price_usd"] = top20["price"].cumsum()
top20_raw = S.rank_candidates(pool, key="residual_pct")
needs_check = S.rank_candidates(pool[pool["residual_pct"] < S.ANOMALY_CAP], n=10_000, key="residual_pct")
cols20 = ["Hang", "id", "date", "zipcode", "price", "predicted_price", "gap_to_prediction_usd", "below_prediction_pct",
          "below_prediction_conservative_pct", "residual", "models_agree_below_20pct", "sqft_living", "bedrooms",
          "bathrooms", "grade", "condition", "view", "waterfront", "house_age", "distance_to_center_km", "lat", "long"]
top20[cols20 + ["cumulative_price_usd"]].to_csv(OUT_T / "top20_candidates_below_prediction_king.csv", index=False, date_format="%Y-%m-%d")
top20_raw[cols20].to_csv(OUT_T / "top20_raw_largest_negative_residual_king.csv", index=False, date_format="%Y-%m-%d")
needs_check[cols20].to_csv(OUT_T / "candidates_need_verification_king.csv", index=False, date_format="%Y-%m-%d")
print(f"Pool sau R1–R3: {len(pool):,} căn | đạt R4–R6: {len(pool_rec):,} | thấp hơn >50% cần xác minh: {len(needs_check)}")
print(f"Tổng giá giao dịch lịch sử 20 căn: {top20['price'].sum():,.0f} USD | tổng giá dự báo: "
      f"{top20['predicted_price'].sum():,.0f} USD | chênh lệch so với giá dự báo: {top20['gap_to_prediction_usd'].sum():,.0f} USD")
print("(Chênh lệch so với dự báo KHÔNG phải lợi nhuận có thể đạt được.)")
top20[["Hang", "id", "zipcode", "price", "predicted_price", "below_prediction_pct",
       "below_prediction_conservative_pct", "sqft_living", "grade", "condition"]]

# %%
fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={"width_ratios": [1.15, 1]})
ax = axes[0]
ax.hist(100 * val["residual_pct"].clip(-0.8, 0.8), bins=80, color=BLUE, alpha=0.85)
ax.axvline(100 * S.BELOW_THRESHOLD, color=ORANGE, lw=2)
ax.annotate(f"ngưỡng −20%:\n{100*val['below_prediction_20pct'].mean():.1f}% giao dịch\nnằm bên trái",
            xy=(100 * S.BELOW_THRESHOLD, ax.get_ylim()[1] * 0.75), xytext=(-75, ax.get_ylim()[1] * 0.75),
            ha="left", va="center", color=INK, fontsize=9, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax.set_xlabel("Residual (%) = giá giao dịch / giá dự báo − 1 (cắt ở ±80%)")
ax.set_ylabel("Số giao dịch")
ax.set_title("Phân phối residual out-of-fold", loc="left")
ax = axes[1]
ax.scatter(val["long"], val["lat"], s=2, color=GRAY, alpha=0.35, linewidths=0, label="Toàn bộ giao dịch")
ax.scatter(top20["long"], top20["lat"], s=60, color=ORANGE, edgecolor="#fcfcfb", linewidth=1.5,
           label="20 ứng viên cần xác minh", zorder=3)
ax.set_xlabel("Kinh độ"); ax.set_ylabel("Vĩ độ")
ax.set_title("Vị trí 20 căn có giá thấp hơn dự báo", loc="left")
leg = ax.legend(loc="lower left", frameon=False, fontsize=9)
leg.legend_handles[0].set_sizes([25]); leg.legend_handles[0].set_alpha(0.8)
savefig(fig, "king_residuals_and_candidates_map")

# %% [markdown]
# ## 6. Phân tích độ nhạy
# ### 6a. What-if: phản ứng của mô hình khi thay một đặc điểm
# Áp lên tập test, giữ nguyên các biến khác, báo trung vị % thay đổi giá dự báo. Kịch bản diện tích giữ đúng
# `sqft_living = sqft_above + sqft_basement` (F06); cột cuối cho biết tỷ lệ dòng ra ngoài miền dữ liệu huấn luyện.
# **Đây là phản ứng của mô hình, không phải tác động nhân quả của cải tạo**; chưa có chi phí, khả năng thực hiện hay
# lợi nhuận ròng, nên chỉ dùng để đặt giả thuyết khảo sát (F07).

# %%
sens_whatif = run_whatif(best_model, X_te, X_tr)
sens_whatif.to_csv(OUT_T / "sensitivity_whatif.csv", index=False)
print(sens_whatif.round(2).to_string(index=False))

# %% [markdown]
# ### 6b. Permutation importance: xáo trộn một biến thì MAPE tăng bao nhiêu điểm %?

# %%
pi = permutation_importance(best_model, X_te, y_te, scoring="neg_mean_absolute_percentage_error",
                            n_repeats=5, random_state=SEED, n_jobs=1)
perm = pd.DataFrame({"Bien": FEATURES, "MAPE_tang_diem_%": 100 * pi.importances_mean,
                     "Do_lech_chuan": 100 * pi.importances_std}).sort_values("MAPE_tang_diem_%", ascending=False)
perm.to_csv(OUT_T / "permutation_importance.csv", index=False)
print(perm.round(2).head(12).to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
fig.subplots_adjust(wspace=0.95)
ax = axes[0]
pt = perm.head(12).iloc[::-1]
ax.barh(pt["Bien"], pt["MAPE_tang_diem_%"], color=BLUE, height=0.6)
ax.set_xlabel("MAPE tăng thêm (điểm %) khi xáo trộn biến")
ax.set_title("12 biến quan trọng nhất", loc="left"); ax.grid(axis="y", visible=False)
ax = axes[1]
sw = sens_whatif.iloc[::-1]
ax.barh(sw["Kich_ban"], sw["Trung_vi_thay_doi_%"],
        color=[BLUE if v >= 0 else ORANGE for v in sw["Trung_vi_thay_doi_%"]], height=0.6)
ax.axvline(0, color=INK, lw=0.8)
for i, v in enumerate(sw["Trung_vi_thay_doi_%"]):
    ax.text(v + (0.3 if v >= 0 else -0.3), i, f"{v:+.1f}%", va="center", ha="left" if v >= 0 else "right",
            fontsize=9, color=INK)
ax.set_xlabel("Trung vị % thay đổi giá dự báo (phản ứng của mô hình)")
ax.set_title("What-if: độ nhạy của giá dự báo", loc="left"); ax.grid(axis="y", visible=False)
ax.set_xlim(min(sw["Trung_vi_thay_doi_%"].min() * 3, -4), sw["Trung_vi_thay_doi_%"].max() * 1.35)
savefig(fig, "king_sensitivity")

# %% [markdown]
# ### 6c. Độ nhạy theo ngưỡng (dữ liệu cho thanh trượt What-if trên Dashboard)

# %%
thr_rows = []
for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
    sel = pool[pool["residual_pct"] <= -t]
    thr_rows.append({"Nguong_%": int(round(100 * t)), "So_can_ung_vien": len(sel),
                     "Ty_le_ung_vien_%": 100 * len(sel) / len(pool),
                     "Ca_3_mo_hinh_dong_y": int((sel[RCOLS] <= -t).all(axis=1).sum()),
                     "Trong_do_thap_hon_qua_50%": int((sel["residual_pct"] < S.ANOMALY_CAP).sum()),
                     "Gia_trung_vi_USD": sel["price"].median() if len(sel) else np.nan,
                     "Du_20_can": len(sel) >= S.N_CANDIDATES})
sens_thr = pd.DataFrame(thr_rows)
sens_thr.to_csv(OUT_T / "sensitivity_threshold.csv", index=False)
print(sens_thr.round(2).to_string(index=False))

# %% [markdown]
# ### 6d. Độ ổn định & tần suất xuất hiện top 20 (F08)
# Mỗi biến thể chạy lại đúng R4–R7, chỉ thay nguồn residual của mô hình chính hoặc cách xếp hạng. Ngoài số căn trùng
# với danh sách chính, lưu **tần suất xuất hiện từng tài sản** qua các biến thể seed để nói về "nhóm lõi".

# %%
resid_other = {"o1": val[RCOLS[1]], "o2": val[RCOLS[2]]}
def ids_for(main_resid, rank="conservative"):
    return S.candidate_ids({"m": main_resid, **resid_other}, pool.index, val["house_age"], val["id"], rank=rank)

base_ids = list(top20["id"])
variants = {"Danh sách chính (TB 4 seed, xếp thận trọng)": base_ids}
for s in SEEDS:
    variants[f"1 seed chia fold = {s}, xếp thận trọng"] = ids_for(val["price"] / oof_seeds[s] - 1)
for s in SEEDS:
    variants[f"1 seed chia fold = {s}, xếp theo riêng mô hình chính"] = ids_for(val["price"] / oof_seeds[s] - 1, rank="main")
variants["Residual từ nested CV, xếp thận trọng"] = ids_for(val["residual_pct_nested"])
seed_variant_names = [k for k in variants if k.startswith("1 seed")]
stab_rows = [{"Bien_the": k, "Trung_voi_ds_chinh": len(set(base_ids) & set(v))} for k, v in variants.items()]
stab_rows.append({"Bien_the": "Xếp theo chênh lệch USD thay vì %",
                  "Trung_voi_ds_chinh": len(set(base_ids) & set(pool_rec.sort_values("residual").head(20)["id"]))})
stab_rows.append({"Bien_the": "Danh sách thô (không lọc R4–R6)", "Trung_voi_ds_chinh": len(set(base_ids) & set(top20_raw["id"]))})
stability = pd.DataFrame(stab_rows)
stability["Ty_le_%"] = 100 * stability["Trung_voi_ds_chinh"] / S.N_CANDIDATES
stability.to_csv(OUT_T / "sensitivity_top20_stability.csv", index=False)
print(stability.to_string(index=False))

freq = S.membership_frequency({k: variants[k] for k in seed_variant_names}, base_ids)
freq.to_csv(OUT_T / "top20_membership_frequency.csv", index=False)
core = freq[freq["Nhom_loi_moi_bien_the"] == 1]
print(f"\nTần suất qua {len(seed_variant_names)} biến thể seed/xếp hạng: {len(freq)} tài sản từng vào top 20; "
      f"{len(core)} căn xuất hiện ở MỌI biến thể; {int(freq.loc[freq.Trong_danh_sach_chinh == 1, 'So_lan_xuat_hien'].ge(len(seed_variant_names) / 2).sum())}/20 "
      f"căn của danh sách chính xuất hiện ở ≥ một nửa biến thể.")

# %% [markdown]
# ## 7. Kiểm chứng phụ trên Ames (Iowa) — điền thiếu học trong Pipeline (F01)
# Không gộp với King County. Loại `sale_type`, `sale_condition` (chỉ biết sau giao dịch), cờ `*_imputed`, mã truy vết
# và biến chứa giá. **Sửa F01:** các ô Ames đã điền trung vị theo neighborhood trong ETL (học trên toàn bộ dữ liệu)
# được trả lại NaN theo `metadata/imputation_audit.csv`; `GroupMedianImputer` học trung vị **chỉ trên train** rồi
# transform test. Điền cấu trúc cố định (NA = không có tiện ích, gara không tồn tại) được giữ vì không học từ dữ liệu.
# Để minh bạch, chạy cả cách cũ (dùng CSV đã điền trước khi chia) và ghi chênh lệch.

# %%
ames, restored_cols = A.load_ames_for_modeling(DATA / "ames_clean.csv", P["metadata"] / "imputation_audit.csv")
A_FEAT, A_NUM, A_CAT = A.ames_feature_lists(ames)
XA, yA = ames[A_FEAT], ames["price"]
a_tr, a_te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(XA, yA, ames["pid"]))
XA_tr, XA_te, yA_tr, yA_te = XA.iloc[a_tr], XA.iloc[a_te], yA.iloc[a_tr], yA.iloc[a_te]
print(f"Ames: {len(A_FEAT)} biến ({len(A_NUM)} số, {len(A_CAT)} phân loại); trả NaN ở {int(XA[restored_cols].isna().sum().sum())} ô "
      f"của {len(restored_cols)} cột: {restored_cols}")
print(f"NaN trong train: {int(XA_tr[restored_cols].isna().sum().sum())} | trong test: {int(XA_te[restored_cols].isna().sum().sum())}")

ames_old = pd.read_csv(DATA / "ames_clean.csv", keep_default_na=False, na_values=[""],
                       dtype={"pid": "string", "ms_subclass": "string"})
XA_old = ames_old[A_FEAT]

ames_rows = [{"Thi_truong": "Ames", "Mo_hinh": "Mốc thô: đơn giá neighborhood × diện tích",
              **metrics(yA_te, XA_te["neighborhood"].map((yA_tr / XA_tr["gr_liv_area"]).groupby(XA_tr["neighborhood"]).median())
                        .fillna((yA_tr / XA_tr["gr_liv_area"]).median()) * XA_te["gr_liv_area"]), "Thoi_gian_fit_s": 0.0}]
ames_compare = []
for kind, name in [("lr", LR_NAME), ("rf", RF_NAME), ("xgb", "XGBoost")]:
    t0 = time.time(); m = A.make_ames_model(kind, A_NUM, A_CAT, seed=SEED).fit(XA_tr, yA_tr)
    new = metrics(yA_te, m.predict(XA_te))
    ames_rows.append({"Thi_truong": "Ames", "Mo_hinh": name, **new, "Thoi_gian_fit_s": time.time() - t0})
    m_old = A.make_ames_model(kind, A_NUM, A_CAT, seed=SEED).fit(XA_old.iloc[a_tr], yA_tr)
    old = metrics(yA_te, m_old.predict(XA_old.iloc[a_te]))
    ames_compare.append({"Mo_hinh": name, "MAPE_cu_dien_truoc_khi_chia_%": old["MAPE_%"],
                         "MAPE_moi_dien_trong_pipeline_%": new["MAPE_%"],
                         "Chenh_lech_diem_%": new["MAPE_%"] - old["MAPE_%"],
                         "RMSE_cu": old["RMSE"], "RMSE_moi": new["RMSE"]})
metrics_ames = pd.DataFrame(ames_rows)
ames_compare = pd.DataFrame(ames_compare)
ames_compare.to_csv(OUT_T / "ames_imputation_fix_comparison.csv", index=False)
# Kiểm tra: đổi tập test không làm đổi trung vị học trên train.
imp = A.make_ames_model("lr", A_NUM, A_CAT).fit(XA_tr, yA_tr).regressor_.named_steps["imp"]
imp2 = A.GroupMedianImputer("neighborhood", A_NUM).fit(XA_tr)
assert imp.group_medians_.equals(imp2.group_medians_)
print(metrics_ames[["Mo_hinh", "MAPE_%", "RMSE", "R2"]].round(3).to_string(index=False))
print(ames_compare.round(3).to_string(index=False))

# %% [markdown]
# ## 8. Lưu mô hình & bảng MAPE tổng hợp
# `models/model.pkl` = mô hình **được chọn bằng CV trên train** (`BEST_NAME`), lấy từ cùng registry, fit lại trên toàn
# bộ dữ liệu King County. Dự báo căn mới qua luồng chính thức (tạo biến + kiểm tra schema):
# `from bds_valuation.predict import load_bundle, predict_prices; predict_prices(df_raw, load_bundle())`.

# %%
all_metrics = pd.concat([metrics_king, metrics_time, pd.DataFrame([nested_metrics]), metrics_ames], ignore_index=True)
all_metrics.to_csv(OUT_T / "model_metrics_mape_report.csv", index=False)

final_model = build_model(BEST_NAME, seed=SEED, params=TUNED.get(BEST_NAME)).fit(X, y)
bundle = {
    "model": final_model, "model_name": BEST_NAME, "metrics_model_name": BEST_NAME,
    "features": FEATURES, "numeric_features": NUM_FEATURES, "categorical_features": CAT_FEATURES,
    "target": "price (USD), mô hình học log(price)", "params": TUNED.get(BEST_NAME),
    "selected_by": "MAPE CV GroupKFold 3 theo id trên train (không dùng tập test)",
    "cv_train_mape": cv_scores, "test_metrics": metrics_king.set_index("Mo_hinh").loc[BEST_NAME].to_dict(),
    "nested_cv_mape_pct": nested_metrics["MAPE_%"],
    "below_prediction_threshold": S.BELOW_THRESHOLD,
    "predict_api": "bds_valuation.predict.predict_prices(df_raw, bundle)",
    "feature_engineering": "bds_valuation.features.engineer_king_features",
    "training_period": [str(king["date"].min().date()), str(king["date"].max().date())],
    "versions": {"python": sys.version.split()[0], "sklearn": sklearn.__version__, "xgboost": xgboost.__version__,
                 "pandas": pd.__version__, "numpy": np.__version__, "joblib": joblib.__version__},
    "trained_on_rows": len(X), "seed": SEED,
}
check_bundle_consistency(bundle)
joblib.dump(bundle, OUT_M / "model.pkl", compress=3)
chk = joblib.load(OUT_M / "model.pkl")
check_bundle_consistency(chk)
assert np.allclose(chk["model"].predict(X.head(50)), final_model.predict(X.head(50)))

summary = {
    "version": "2 (sửa theo feedback F01–F12)", "fast_mode": FAST,
    "best_model": BEST_NAME, "selected_by": bundle["selected_by"], "cv_train_mape_pct": cv_scores,
    "xgb_best_params": BEST_XGB,
    "test_split": {"train_rows": len(X_tr), "test_rows": len(X_te), "split": "GroupShuffleSplit theo id, 80/20, seed 42"},
    "king_test_metrics": metrics_king.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
    "king_temporal_backtest": {**metrics_time.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
                               "info": temporal_info},
    "king_nested_cv": {"MAPE_%": round(nested_metrics["MAPE_%"], 4), "RMSE": round(nested_metrics["RMSE"], 1),
                       "R2": round(nested_metrics["R2"], 4),
                       "chosen_per_fold": nested_folds["chosen_model"].tolist()},
    "ames_test_metrics": metrics_ames.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
    "ames_imputation_fix": ames_compare.round(4).to_dict("records"),
    "oof_screening_mape_pct": round(100 * mean_absolute_percentage_error(y, oof_best), 3),
    "below_prediction_rate_pct_all_transactions": round(100 * val["below_prediction_20pct"].mean(), 3),
    "candidate_pool_size": len(pool), "recommended_pool_size": len(pool_rec),
    "needs_verification_count": len(needs_check), "anomaly_cap_pct": 100 * S.ANOMALY_CAP,
    "top20_raw_total_price_usd": float(top20_raw["price"].sum()),
    "top20_total_historical_price_usd": float(top20["price"].sum()),
    "top20_total_predicted_usd": float(top20["predicted_price"].sum()),
    "top20_gap_to_prediction_usd": float(top20["gap_to_prediction_usd"].sum()),
    "top20_gap_note": "Chênh lệch so với giá dự báo trên giao dịch lịch sử; không phải lợi nhuận có thể đạt được.",
    "top20_all_three_models_agree": int((top20["models_agree_below_20pct"] == 3).sum()),
    "top20_core_all_seed_variants": int(len(core)),
    "seed_variants_counted": len(seed_variant_names),
}
(OUT_T / "task4_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("best_model", "cv_train_mape_pct", "king_nested_cv", "oof_screening_mape_pct",
                                          "top20_total_historical_price_usd", "top20_total_predicted_usd")},
                 ensure_ascii=False, indent=2, default=float))
