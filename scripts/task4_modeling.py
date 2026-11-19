# %% [markdown]
# # Nhiệm vụ 4 — Mô hình dự báo giá & danh sách 20 căn bị định giá thấp
# Chủ đề 14: Mô hình định giá bất động sản tự động.
#
# **Đầu vào:** dữ liệu sạch của Nhiệm vụ 2 (`data/processed/*.csv`).
# **Đầu ra:** `models/model.pkl`, `outputs/task4/tables/*`, `outputs/task4/figures/*`.
#
# Quy trình:
# 1. Đọc dữ liệu, tạo biến cho mô hình, loại các biến rò rỉ giá (`price_per_sqft`, `price_iqr_outlier`).
# 2. Chia train/test 80/20 **theo id tài sản** (một căn bán nhiều lần không nằm ở cả hai phía).
# 3. Mốc so sánh thô (trung vị đơn giá theo zipcode), Baseline Linear Regression, Random Forest, XGBoost (tinh chỉnh bằng CV).
# 4. Đánh giá MAPE, RMSE, MAE, R² trên tập test; MAPE theo phân khúc giá; kiểm tra chia theo thời gian.
# 5. Dự báo **out-of-fold** (5-fold theo id) cho toàn bộ giao dịch → residual → 20 căn có residual âm lớn nhất.
# 6. Phân tích độ nhạy: what-if từng biến, permutation importance, ngưỡng %, độ ổn định top 20.
# 7. Kiểm chứng phụ trên Ames.

# %%
import json
import time
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (mean_absolute_error, mean_absolute_percentage_error,
                             mean_squared_error, r2_score)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (FunctionTransformer, OneHotEncoder, OrdinalEncoder,
                                   StandardScaler)
from xgboost import XGBRegressor

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path.cwd()
if not (ROOT / "data").exists():          # chạy từ notebooks/ hoặc scripts/
    ROOT = ROOT.parent
DATA = ROOT / "data" / "processed"
OUT_T = ROOT / "outputs" / "task4" / "tables"
OUT_F = ROOT / "outputs" / "task4" / "figures"
OUT_M = ROOT / "models"
for p in (OUT_T, OUT_F, OUT_M):
    p.mkdir(parents=True, exist_ok=True)

SEED = 42
UNDERVALUE_THRESHOLD = -0.20     # giá bán thấp hơn giá trị mô hình ≥ 20%
N_CANDIDATES = 20                # ràng buộc: Giám đốc đầu tư chọn 20 căn

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

def metrics(y_true, y_pred):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    ape = np.abs(y_pred - y_true) / y_true
    return {
        "MAPE_%": 100 * mean_absolute_percentage_error(y_true, y_pred),
        "MdAPE_%": 100 * np.median(ape),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": mean_absolute_error(y_true, y_pred),
        "R2": r2_score(y_true, y_pred),
        "Ty_le_sai_<=10%": 100 * np.mean(ape <= 0.10),
        "Ty_le_sai_<=20%": 100 * np.mean(ape <= 0.20),
    }

print("pandas", pd.__version__, "| sklearn", sklearn.__version__, "| xgboost", xgboost.__version__)

# %% [markdown]
# ## 1. Đọc dữ liệu King County và tạo biến
# Đọc đúng kiểu theo `docs/data_handoff.txt`. Các biến thêm cho mô hình (chỉ dùng thông tin có trước giao dịch):
# - `is_renovated`, `years_since_update` = năm bán − max(năm xây, năm cải tạo)
# - `month_index` = số tháng kể từ 05/2014 (bắt xu hướng thị trường)
#
# Loại khỏi X: `price` (mục tiêu), `price_per_sqft`, `price_iqr_outlier` (chứa giá), các mã truy vết.

# %%
king = pd.read_csv(DATA / "king_county_clean.csv", dtype={"id": "string", "zipcode": "string"})
king["date"] = pd.to_datetime(king["date"])
king["is_renovated"] = (king["yr_renovated"] > 0).astype(int)
king["years_since_update"] = (king["sale_year"] - king[["yr_built", "yr_renovated"]].max(axis=1)).clip(lower=0)
king["month_index"] = (king["date"].dt.year - 2014) * 12 + king["date"].dt.month - 5

NUM_FEATURES = ["bedrooms", "bathrooms", "sqft_living", "sqft_lot", "floors", "waterfront", "view",
                "condition", "grade", "sqft_above", "sqft_basement", "house_age", "is_renovated",
                "years_since_update", "lat", "long", "distance_to_center_km", "sqft_living15",
                "sqft_lot15", "month_index"]
CAT_FEATURES = ["zipcode"]
FEATURES = NUM_FEATURES + CAT_FEATURES
LOG_COLS = ["sqft_living", "sqft_lot", "sqft_above", "sqft_living15", "sqft_lot15", "distance_to_center_km"]
LEAKAGE = {"price", "price_per_sqft", "price_iqr_outlier"}
assert not LEAKAGE & set(FEATURES), "Biến rò rỉ giá nằm trong X!"

X, y, groups = king[FEATURES], king["price"], king["id"]
print(f"King County: {len(king):,} giao dịch, {king['id'].nunique():,} tài sản, {len(FEATURES)} biến đầu vào")

# %% [markdown]
# ## 2. Chia train/test theo id tài sản

# %%
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
tr_idx, te_idx = next(gss.split(X, y, groups))
X_tr, X_te, y_tr, y_te = X.iloc[tr_idx], X.iloc[te_idx], y.iloc[tr_idx], y.iloc[te_idx]
g_tr = groups.iloc[tr_idx]
assert not set(g_tr) & set(groups.iloc[te_idx])
print(f"Train {len(X_tr):,} | Test {len(X_te):,} | id trùng giữa hai tập: 0")

# %% [markdown]
# ## 3. Xây dựng mô hình
# Mọi mô hình học trên **log(price)** (giá lệch phải mạnh) rồi đổi ngược về USD khi dự báo —
# `TransformedTargetRegressor` lo việc này, nên MAPE/RMSE được tính trên giá thật.
# Mọi bước tiền xử lý nằm trong Pipeline và chỉ fit trên train (tránh rò rỉ).

# %%
def make_linear():
    pre = ColumnTransformer([
        ("log", Pipeline([("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                          ("sc", StandardScaler())]), LOG_COLS),
        ("num", StandardScaler(), [c for c in NUM_FEATURES if c not in LOG_COLS]),
        ("zip", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
    ])
    return TransformedTargetRegressor(Pipeline([("pre", pre), ("model", LinearRegression())]),
                                      func=np.log, inverse_func=np.exp)

def tree_pre():
    return ColumnTransformer([
        ("num", "passthrough", NUM_FEATURES),
        ("zip", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT_FEATURES),
    ], verbose_feature_names_out=False)

def make_rf(seed=SEED):
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features=0.5,
                               n_jobs=-1, random_state=seed)
    return TransformedTargetRegressor(Pipeline([("pre", tree_pre()), ("model", rf)]),
                                      func=np.log, inverse_func=np.exp)

def make_xgb(params=None, seed=SEED):
    base = dict(n_estimators=1500, learning_rate=0.03, max_depth=6, min_child_weight=3,
                subsample=0.8, colsample_bytree=0.7, reg_lambda=1.0, tree_method="hist",
                n_jobs=-1, random_state=seed)
    base.update(params or {})
    return TransformedTargetRegressor(Pipeline([("pre", tree_pre()), ("model", XGBRegressor(**base))]),
                                      func=np.log, inverse_func=np.exp)

# %% [markdown]
# ### 3a. Mốc so sánh thô: trung vị đơn giá theo zipcode × diện tích
# Đây là cách "định giá thủ công" của môi giới. Mô hình phải tốt hơn mốc này mới có giá trị.

# %%
ppsf_tr = (y_tr / X_tr["sqft_living"]).groupby(X_tr["zipcode"]).median()
naive_pred = X_te["zipcode"].map(ppsf_tr).fillna((y_tr / X_tr["sqft_living"]).median()) * X_te["sqft_living"]

# %% [markdown]
# ### 3b. Tinh chỉnh XGBoost (RandomizedSearch, 3-fold theo id, chỉ trên train)

# %%
t0 = time.time()
search = RandomizedSearchCV(
    make_xgb(),
    param_distributions={
        "regressor__model__max_depth": [4, 5, 6, 7, 8],
        "regressor__model__learning_rate": [0.02, 0.03, 0.05],
        "regressor__model__n_estimators": [800, 1200, 1800],
        "regressor__model__min_child_weight": [1, 3, 5, 10],
        "regressor__model__subsample": [0.7, 0.8, 0.9],
        "regressor__model__colsample_bytree": [0.5, 0.7, 0.9],
        "regressor__model__reg_lambda": [0.5, 1.0, 3.0, 10.0],
    },
    n_iter=20, cv=GroupKFold(n_splits=3), scoring="neg_mean_absolute_percentage_error",
    random_state=SEED, n_jobs=1, refit=False,
)
search.fit(X_tr, y_tr, groups=g_tr)
BEST_XGB = {k.replace("regressor__model__", ""): v for k, v in search.best_params_.items()}
print(f"Tinh chỉnh xong sau {time.time()-t0:.0f}s — CV MAPE tốt nhất = {-100*search.best_score_:.2f}%")
print("Tham số tốt nhất:", BEST_XGB)
pd.DataFrame(search.cv_results_).sort_values("rank_test_score")[
    ["rank_test_score", "mean_test_score", "std_test_score", "params"]
].assign(mean_test_MAPE_pct=lambda d: -100 * d["mean_test_score"]).to_csv(OUT_T / "xgb_tuning_results.csv", index=False)

# %% [markdown]
# ### 3c. Huấn luyện và đánh giá trên tập test

# %%
models = {"Linear Regression (baseline)": make_linear(),
          "Random Forest": make_rf(),
          "XGBoost (tuned)": make_xgb(BEST_XGB)}
preds = {"Mốc thô: đơn giá zipcode × diện tích": naive_pred.values}
fit_time = {}
for name, m in models.items():
    t0 = time.time()
    m.fit(X_tr, y_tr)
    fit_time[name] = time.time() - t0
    preds[name] = m.predict(X_te)

metric_rows = [{"Thi_truong": "King County", "Mo_hinh": n, **metrics(y_te, p),
                "Thoi_gian_fit_s": fit_time.get(n, 0.0)} for n, p in preds.items()]
metrics_king = pd.DataFrame(metric_rows)
print(metrics_king.round(3).to_string(index=False))

BEST_NAME = metrics_king.iloc[1:].sort_values("MAPE_%").iloc[0]["Mo_hinh"]
best_model = models[BEST_NAME]
print("\nMô hình tốt nhất theo MAPE:", BEST_NAME)

# %% [markdown]
# ### 3d. MAPE theo phân khúc giá (mô hình tốt nhất có kém ở phân khúc nào không?)

# %%
seg = pd.qcut(y_te, 5, labels=["Q1 rẻ nhất", "Q2", "Q3", "Q4", "Q5 đắt nhất"])
seg_rows = []
for name in ["Linear Regression (baseline)", BEST_NAME]:
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
# ### 3e. Kiểm tra theo thời gian: train trước 01/02/2015, test từ 01/02/2015
# Mô phỏng tình huống thật: học quá khứ, định giá giao dịch tương lai.

# %%
cut = pd.Timestamp("2015-02-01")
past, future = king["date"] < cut, king["date"] >= cut
future &= ~king["id"].isin(king.loc[past, "id"])     # bỏ căn đã xuất hiện trong quá khứ
time_rows = []
for name, maker in [("Linear Regression (baseline)", make_linear),
                    ("XGBoost (tuned)", lambda: make_xgb(BEST_XGB))]:
    m = maker().fit(X[past], y[past])
    time_rows.append({"Thi_truong": "King County (chia theo thời gian)", "Mo_hinh": name,
                      **metrics(y[future], m.predict(X[future])), "Thoi_gian_fit_s": np.nan})
metrics_time = pd.DataFrame(time_rows)
print(f"Train {past.sum():,} giao dịch trước {cut.date()}, test {future.sum():,} giao dịch sau")
print(metrics_time[["Mo_hinh", "MAPE_%", "RMSE", "R2"]].round(3).to_string(index=False))

# %% [markdown]
# ### 3f. Biểu đồ: so sánh mô hình, thực tế vs dự báo

# %%
fig, ax = plt.subplots(figsize=(7.5, 3.4))
mk = metrics_king.sort_values("MAPE_%", ascending=True)
colors = [BLUE if n == BEST_NAME else GRAY for n in mk["Mo_hinh"]]
bars = ax.barh(mk["Mo_hinh"], mk["MAPE_%"], color=colors, height=0.55)
ax.invert_yaxis()
for b, v in zip(bars, mk["MAPE_%"]):
    ax.text(v + 0.3, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", color=INK, fontsize=10)
ax.set_xlabel("MAPE trên tập test (%) — càng thấp càng tốt")
ax.set_title("King County: sai số phần trăm tuyệt đối trung bình theo mô hình", loc="left")
ax.grid(axis="y", visible=False)
savefig(fig, "king_model_comparison_mape")

fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharex=True, sharey=True)
for ax, name in zip(axes, ["Linear Regression (baseline)", BEST_NAME]):
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
# ## 4. Residual out-of-fold cho toàn bộ giao dịch
# Nếu tính residual trên chính dữ liệu đã train, mô hình đã "học thuộc" giá căn đó nên residual bị thu nhỏ.
# Vì vậy mỗi giao dịch được định giá bởi mô hình **chưa từng thấy tài sản đó** (GroupKFold 5 phần theo id).
#
# `residual = giá thực − giá mô hình`; `residual_pct = giá thực / giá mô hình − 1`.
# Căn có residual_pct ≤ −20% được coi là **bị định giá thấp** (ứng viên).

# %%
def oof_predict(maker, seed=SEED, n_splits=5):
    oof = np.zeros(len(X))
    for k, (a, b) in enumerate(GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y, groups)):
        oof[b] = maker(seed).fit(X.iloc[a], y.iloc[a]).predict(X.iloc[b])
    return oof

# Mô hình chính: trung bình 4 lần OOF với 4 seed chia fold khác nhau (giảm nhiễu do cách chia fold).
SEEDS = [42, 1, 7, 2024]
best_maker = (lambda s: make_xgb(BEST_XGB, seed=s)) if BEST_NAME.startswith("XGB") else (lambda s: make_rf(seed=s))
t0 = time.time()
oof_seeds = {s: oof_predict(best_maker, seed=s) for s in SEEDS}
oof_best = np.mean(list(oof_seeds.values()), axis=0)
oof_rf = oof_predict(lambda s: make_rf(seed=s))
oof_lr = oof_predict(lambda s: make_linear())
print(f"OOF xong sau {time.time()-t0:.0f}s")
print("OOF MAPE — mô hình chính: %.2f%% | RF: %.2f%% | LR: %.2f%%" % tuple(
    100 * mean_absolute_percentage_error(y, o) for o in (oof_best, oof_rf, oof_lr)))

val = king[["source_row_id", "id", "date", "price", "zipcode", "lat", "long", "bedrooms", "bathrooms",
            "sqft_living", "sqft_lot", "grade", "condition", "view", "waterfront", "house_age",
            "is_renovated", "distance_to_center_km", "zero_room_flag"]].copy()
val["predicted_price"] = oof_best.round(0)
val["residual"] = (val["price"] - val["predicted_price"]).round(0)
val["residual_pct"] = val["price"] / val["predicted_price"] - 1
val["residual_pct_rf"] = val["price"] / oof_rf - 1
val["residual_pct_lr"] = val["price"] / oof_lr - 1
# Mức giảm thận trọng: residual "ít âm nhất" trong 3 mô hình — căn chỉ xếp cao khi CẢ 3 cùng thấy rẻ.
val["residual_pct_conservative"] = val[["residual_pct", "residual_pct_rf", "residual_pct_lr"]].max(axis=1)
val["undervalued_20pct"] = (val["residual_pct"] <= UNDERVALUE_THRESHOLD).astype(int)
val["models_agree_undervalued"] = ((val[["residual_pct", "residual_pct_rf", "residual_pct_lr"]]
                                    <= UNDERVALUE_THRESHOLD).sum(axis=1))
val["is_latest_sale"] = (val["date"] == val.groupby("id")["date"].transform("max")).astype(int)
val.to_csv(OUT_T / "king_oof_predictions.csv", index=False, date_format="%Y-%m-%d")
print(f"Tỷ lệ giao dịch bị định giá thấp ≥20%: {100*val['undervalued_20pct'].mean():.2f}% "
      f"({val['undervalued_20pct'].sum():,} giao dịch)")

# %% [markdown]
# ## 5. Danh sách 20 căn ứng viên
# Quy tắc chọn (ghi rõ để Giám đốc đầu tư kiểm tra):
# 1. Chỉ xét **giao dịch gần nhất** của mỗi tài sản (không chọn trùng một căn).
# 2. Loại căn có cờ `zero_room_flag` (0 phòng ngủ/tắm — nghi dữ liệu lỗi) và căn `condition ≤ 2`
#    (giá thấp do hư hỏng là có lý do, không phải "định giá sai").
# 3. Xếp theo `residual_pct` tăng dần (âm nhất trước). Dùng % thay vì USD để không thiên vị nhà đắt.
#
# **Danh sách thô** = 20 căn đầu theo quy tắc trên (đúng định nghĩa "residual âm lớn nhất").
# Tuy nhiên đuôi cực trị (giảm > 50%, xa hơn rất nhiều so với sai số điển hình ~7–11% của mô hình)
# thường là giao dịch không theo thị trường (bán cho người thân, thừa kế, bán tháo, bán khi nhà
# chưa xây xong) hoặc lỗi nhập liệu — không phải cơ hội mua được. Vì vậy **danh sách khuyến nghị** thêm:
# 4. Mức giảm trong khoảng 20%–50% (căn giảm > 50% chuyển sang file "cần xác minh").
# 5. Cả 3 mô hình (XGBoost, RF, LR) cùng cho residual ≤ −20% (đồng thuận, giảm rủi ro sai do một mô hình).
# 6. Loại nhà tuổi 0 (bán khi đang/vừa xây, giá có thể là giá đất/giá đặt cọc).
# 7. Xếp theo **mức giảm thận trọng** = mức giảm nhỏ nhất trong 3 mô hình (ổn định hơn xếp theo 1 mô hình).

# %%
ANOMALY_CAP = -0.50
pool = val[(val["is_latest_sale"] == 1) & (val["zero_room_flag"] == 0) & (val["condition"] >= 3)]
pool_rec = pool[(pool["residual_pct"] >= ANOMALY_CAP) & (pool["models_agree_undervalued"] == 3)
                & (pool["house_age"] > 0)]
cols20 = ["Hang", "id", "date", "zipcode", "price", "predicted_price", "upside_usd", "discount_pct",
          "discount_conservative_pct", "residual", "models_agree_undervalued", "sqft_living", "bedrooms",
          "bathrooms", "grade", "condition", "view", "waterfront", "house_age", "distance_to_center_km",
          "lat", "long"]

def make_list(frame, n=N_CANDIDATES, key="residual_pct"):
    t = frame.sort_values(key).head(n).copy()
    t.insert(0, "Hang", range(1, len(t) + 1))
    t["discount_pct"] = (-100 * t["residual_pct"]).round(1)
    t["discount_conservative_pct"] = (-100 * t["residual_pct_conservative"]).round(1)
    t["upside_usd"] = (t["predicted_price"] - t["price"]).round(0)
    return t[cols20]

top20_raw = make_list(pool)
top20 = make_list(pool_rec, key="residual_pct_conservative")
top20["cumulative_cost_usd"] = top20["price"].cumsum()
needs_check = make_list(pool[pool["residual_pct"] < ANOMALY_CAP], n=10_000)
top20.to_csv(OUT_T / "top20_undervalued_king.csv", index=False, date_format="%Y-%m-%d")
top20_raw.to_csv(OUT_T / "top20_raw_largest_negative_residual_king.csv", index=False, date_format="%Y-%m-%d")
needs_check.to_csv(OUT_T / "candidates_need_verification_king.csv", index=False, date_format="%Y-%m-%d")
print(f"Pool sau lọc cơ bản: {len(pool):,} căn | đạt điều kiện khuyến nghị: {len(pool_rec):,} | "
      f"giảm >50% cần xác minh: {len(needs_check)}")
print(f"Danh sách thô trùng với danh sách khuyến nghị: {len(set(top20_raw['id']) & set(top20['id']))}/20")
print(f"Tổng vốn mua 20 căn: {top20['price'].sum():,.0f} USD | "
      f"Giá trị mô hình: {top20['predicted_price'].sum():,.0f} USD | "
      f"Chênh lệch kỳ vọng: {top20['upside_usd'].sum():,.0f} USD")
print(f"Số căn cả 3 mô hình cùng đồng ý: {(top20['models_agree_undervalued'] == 3).sum()} / 20")
top20[["Hang", "id", "zipcode", "price", "predicted_price", "discount_pct", "models_agree_undervalued",
       "sqft_living", "grade", "condition"]]

# %%
fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={"width_ratios": [1.15, 1]})
ax = axes[0]
ax.hist(100 * val["residual_pct"].clip(-0.8, 0.8), bins=80, color=BLUE, alpha=0.85)
ax.axvline(100 * UNDERVALUE_THRESHOLD, color=ORANGE, lw=2)
ax.annotate(f"ngưỡng −20%:\n{100*val['undervalued_20pct'].mean():.1f}% giao dịch\nnằm bên trái",
            xy=(100 * UNDERVALUE_THRESHOLD, ax.get_ylim()[1] * 0.75), xytext=(-75, ax.get_ylim()[1] * 0.75),
            ha="left", va="center", color=INK, fontsize=9,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax.set_xlabel("Residual (%) = giá thực / giá mô hình − 1 (cắt ở ±80%)")
ax.set_ylabel("Số giao dịch")
ax.set_title("Phân phối residual out-of-fold", loc="left")
ax = axes[1]
ax.scatter(val["long"], val["lat"], s=2, color=GRAY, alpha=0.35, linewidths=0, label="Toàn bộ giao dịch")
ax.scatter(top20["long"], top20["lat"], s=60, color=ORANGE, edgecolor="#fcfcfb", linewidth=1.5,
           label="20 căn ứng viên", zorder=3)
ax.set_xlabel("Kinh độ"); ax.set_ylabel("Vĩ độ")
ax.set_title("Vị trí 20 căn bị định giá thấp", loc="left")
leg = ax.legend(loc="lower left", frameon=False, fontsize=9)
leg.legend_handles[0].set_sizes([25]); leg.legend_handles[0].set_alpha(0.8)
savefig(fig, "king_residuals_and_candidates_map")

# %% [markdown]
# ## 6. Phân tích độ nhạy
# ### 6a. What-if: thay đổi một đặc điểm, giá dự báo thay đổi bao nhiêu %?
# Áp lên toàn bộ tập test, giữ nguyên các biến khác; báo trung vị % thay đổi giá dự báo.

# %%
base_pred = best_model.predict(X_te)
scenarios = {
    "Diện tích ở +10%": lambda d: d.assign(sqft_living=d.sqft_living * 1.1, sqft_above=d.sqft_above * 1.1),
    "Grade (chất lượng xây) +1": lambda d: d.assign(grade=(d.grade + 1).clip(upper=13)),
    "Condition (tình trạng) +1": lambda d: d.assign(condition=(d.condition + 1).clip(upper=5)),
    "View +1 bậc": lambda d: d.assign(view=(d.view + 1).clip(upper=4)),
    "Thêm 1 phòng tắm": lambda d: d.assign(bathrooms=d.bathrooms + 1),
    "Thêm 1 phòng ngủ (cùng diện tích)": lambda d: d.assign(bedrooms=d.bedrooms + 1),
    "Tuổi nhà +10 năm": lambda d: d.assign(house_age=d.house_age + 10, years_since_update=d.years_since_update + 10),
    "Cải tạo mới (years_since_update = 0)": lambda d: d.assign(is_renovated=1, years_since_update=0),
    "Thời điểm bán +6 tháng": lambda d: d.assign(month_index=d.month_index + 6),
    "Diện tích đất +20%": lambda d: d.assign(sqft_lot=d.sqft_lot * 1.2),
}
sens_rows = []
for sc, f in scenarios.items():
    chg = best_model.predict(f(X_te.copy())) / base_pred - 1
    sens_rows.append({"Kich_ban": sc, "Trung_vi_thay_doi_%": 100 * np.median(chg),
                      "Trung_binh_thay_doi_%": 100 * chg.mean(),
                      "P10_%": 100 * np.percentile(chg, 10), "P90_%": 100 * np.percentile(chg, 90)})
sens_whatif = pd.DataFrame(sens_rows).sort_values("Trung_vi_thay_doi_%", ascending=False)
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

fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
fig.subplots_adjust(wspace=0.75)
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
ax.set_xlabel("Trung vị % thay đổi giá dự báo")
ax.set_title("What-if: độ nhạy của giá dự báo", loc="left"); ax.grid(axis="y", visible=False)
ax.set_xlim(min(sw["Trung_vi_thay_doi_%"].min() * 3, -4), sw["Trung_vi_thay_doi_%"].max() * 1.35)
savefig(fig, "king_sensitivity")

# %% [markdown]
# ### 6c. Độ nhạy theo ngưỡng undervalued (dữ liệu cho thanh trượt What-if trên Dashboard)

# %%
thr_rows = []
RCOLS = ["residual_pct", "residual_pct_rf", "residual_pct_lr"]
for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
    sel = pool[pool["residual_pct"] <= -t]
    thr_rows.append({"Nguong_%": int(100 * t), "So_can_ung_vien": len(sel),
                     "Ty_le_ung_vien_%": 100 * len(sel) / len(pool),
                     "Ca_3_mo_hinh_dong_y": int((sel[RCOLS] <= -t).all(axis=1).sum()),
                     "Trong_do_giam_qua_50%": int((sel["residual_pct"] < ANOMALY_CAP).sum()),
                     "Gia_trung_vi_USD": sel["price"].median() if len(sel) else np.nan,
                     "Du_20_can": len(sel) >= N_CANDIDATES})
sens_thr = pd.DataFrame(thr_rows)
sens_thr.to_csv(OUT_T / "sensitivity_threshold.csv", index=False)
print(sens_thr.round(2).to_string(index=False))

# %% [markdown]
# ### 6d. Độ ổn định top 20: đổi seed chia fold / đổi mô hình thì danh sách giữ được bao nhiêu căn?

# %%
# Mỗi biến thể chạy lại đúng quy tắc chọn khuyến nghị, chỉ thay nguồn residual của mô hình chính.
def rec_ids(main_resid, rank="conservative", n=N_CANDIDATES):
    r = pd.DataFrame({"m": np.asarray(main_resid), "rf": val["residual_pct_rf"], "lr": val["residual_pct_lr"]},
                     index=val.index).loc[pool.index]
    ok = (r["m"] >= ANOMALY_CAP) & (r[["m", "rf", "lr"]] <= UNDERVALUE_THRESHOLD).all(axis=1) & (pool["house_age"] > 0)
    key = r[["m", "rf", "lr"]].max(axis=1) if rank == "conservative" else r["m"]
    return set(val.loc[key[ok].sort_values().head(n).index, "id"])

base_ids = set(top20["id"])
stab_rows = [{"Bien_the": "Danh sách chính (XGBoost TB 4 seed, xếp theo mức giảm thận trọng)", "Trung_voi_ds_chinh": 20}]
for s in SEEDS:
    stab_rows.append({"Bien_the": f"Chỉ dùng XGBoost 1 seed chia fold = {s}",
                      "Trung_voi_ds_chinh": len(base_ids & rec_ids(val["price"] / oof_seeds[s] - 1))})
stab_rows.append({"Bien_the": "Xếp theo residual của riêng XGBoost (không thận trọng)",
                  "Trung_voi_ds_chinh": len(base_ids & rec_ids(val["residual_pct"], rank="main"))})
for s in [1, 7]:
    stab_rows.append({"Bien_the": f"XGBoost 1 seed {s} + xếp theo riêng XGBoost",
                      "Trung_voi_ds_chinh": len(base_ids & rec_ids(val["price"] / oof_seeds[s] - 1, rank="main"))})
stab_rows.append({"Bien_the": "Xếp theo residual USD thay vì %",
                  "Trung_voi_ds_chinh": len(base_ids & set(pool_rec.sort_values("residual").head(20)["id"]))})
stab_rows.append({"Bien_the": "Danh sách thô (không lọc bất thường)",
                  "Trung_voi_ds_chinh": len(base_ids & set(top20_raw["id"]))})
stability = pd.DataFrame(stab_rows)
stability["Ty_le_%"] = 100 * stability["Trung_voi_ds_chinh"] / N_CANDIDATES
stability.to_csv(OUT_T / "sensitivity_top20_stability.csv", index=False)
print(stability.to_string(index=False))

# %% [markdown]
# ## 7. Kiểm chứng phụ trên Ames (Iowa)
# Không gộp với King County (khác thị trường, khác định nghĩa diện tích). Chỉ dùng để xem
# quy trình có cho kết quả tương tự ở thị trường khác không. Loại `sale_type`, `sale_condition`
# (chỉ biết sau khi giao dịch), cờ `*_imputed`, mã truy vết và các biến chứa giá.

# %%
ames = pd.read_csv(DATA / "ames_clean.csv", keep_default_na=False, na_values=[""],
                   dtype={"pid": "string", "ms_subclass": "string"})
drop = {"source_row_id", "order", "pid", "sale_price", "price", "price_per_sqft", "price_iqr_outlier",
        "sale_type", "sale_condition", "distance_to_center_km", "distance_available", "raw_house_age",
        "has_any_imputation", "has_true_imputation", "sqft_living"} | {c for c in ames if c.endswith("_imputed")}
A_FEAT = [c for c in ames.columns if c not in drop]
A_CAT = [c for c in A_FEAT if not pd.api.types.is_numeric_dtype(ames[c])]
A_NUM = [c for c in A_FEAT if c not in A_CAT]
XA, yA = ames[A_FEAT], ames["price"]
XA_tr, XA_te, yA_tr, yA_te = (lambda i: (XA.iloc[i[0]], XA.iloc[i[1]], yA.iloc[i[0]], yA.iloc[i[1]]))(
    next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(XA, yA, ames["pid"])))

def ames_model(kind):
    if kind == "lr":
        pre = ColumnTransformer([("num", StandardScaler(), A_NUM),
                                 ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), A_CAT)])
        reg = LinearRegression()
    else:
        pre = ColumnTransformer([("num", "passthrough", A_NUM),
                                 ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), A_CAT)])
        reg = (RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features=0.5, n_jobs=-1, random_state=SEED)
               if kind == "rf" else
               XGBRegressor(n_estimators=1200, learning_rate=0.03, max_depth=4, min_child_weight=3, subsample=0.8,
                            colsample_bytree=0.5, tree_method="hist", n_jobs=-1, random_state=SEED))
    return TransformedTargetRegressor(Pipeline([("pre", pre), ("model", reg)]), func=np.log, inverse_func=np.exp)

ames_rows = [{"Thi_truong": "Ames", "Mo_hinh": "Mốc thô: đơn giá neighborhood × diện tích",
              **metrics(yA_te, XA_te["neighborhood"].map((yA_tr / XA_tr["gr_liv_area"]).groupby(XA_tr["neighborhood"]).median())
                        .fillna((yA_tr / XA_tr["gr_liv_area"]).median()) * XA_te["gr_liv_area"]), "Thoi_gian_fit_s": 0.0}]
for kind, name in [("lr", "Linear Regression (baseline)"), ("rf", "Random Forest"), ("xgb", "XGBoost")]:
    t0 = time.time(); m = ames_model(kind).fit(XA_tr, yA_tr)
    ames_rows.append({"Thi_truong": "Ames", "Mo_hinh": name, **metrics(yA_te, m.predict(XA_te)),
                      "Thoi_gian_fit_s": time.time() - t0})
metrics_ames = pd.DataFrame(ames_rows)
print(f"Ames: {len(A_FEAT)} biến ({len(A_NUM)} số, {len(A_CAT)} phân loại)")
print(metrics_ames[["Mo_hinh", "MAPE_%", "RMSE", "R2"]].round(3).to_string(index=False))

# %% [markdown]
# ## 8. Lưu mô hình & bảng MAPE tổng hợp
# `models/model.pkl` = mô hình tốt nhất King County, **đã fit lại trên toàn bộ dữ liệu** để dùng định giá căn mới.
# Đọc lại: `bundle = joblib.load('models/model.pkl'); bundle['model'].predict(df[bundle['features']])`.
# (Cần tạo trước 3 biến `is_renovated`, `years_since_update`, `month_index` như mục 1.)

# %%
all_metrics = pd.concat([metrics_king, metrics_time, metrics_ames], ignore_index=True)
all_metrics.to_csv(OUT_T / "model_metrics_mape_report.csv", index=False)

final_model = (make_xgb(BEST_XGB) if BEST_NAME.startswith("XGB") else make_rf()).fit(X, y)
bundle = {
    "model": final_model, "model_name": BEST_NAME, "features": FEATURES,
    "numeric_features": NUM_FEATURES, "categorical_features": CAT_FEATURES,
    "target": "price (USD), mô hình học log(price)", "xgb_params": BEST_XGB,
    "test_metrics": metrics_king.set_index("Mo_hinh").loc[BEST_NAME].to_dict(),
    "undervalue_threshold": UNDERVALUE_THRESHOLD,
    "engineered_features": {
        "is_renovated": "1 nếu yr_renovated > 0",
        "years_since_update": "sale_year - max(yr_built, yr_renovated), chặn dưới 0",
        "month_index": "(năm bán - 2014)*12 + tháng bán - 5",
    },
    "versions": {"python_sklearn": sklearn.__version__, "xgboost": xgboost.__version__, "pandas": pd.__version__},
    "trained_on_rows": len(X),
}
joblib.dump(bundle, OUT_M / "model.pkl", compress=3)
chk = joblib.load(OUT_M / "model.pkl")
assert np.allclose(chk["model"].predict(X.head(50)), final_model.predict(X.head(50)))

summary = {
    "best_model": BEST_NAME, "xgb_best_params": BEST_XGB,
    "test_split": {"train_rows": len(X_tr), "test_rows": len(X_te), "split": "GroupShuffleSplit theo id, 80/20, seed 42"},
    "king_test_metrics": metrics_king.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
    "king_time_split_metrics": metrics_time.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
    "ames_test_metrics": metrics_ames.set_index("Mo_hinh")[["MAPE_%", "RMSE", "R2"]].round(4).to_dict("index"),
    "oof_mape_pct": round(100 * mean_absolute_percentage_error(y, oof_best), 3),
    "undervalued_rate_pct_all_transactions": round(100 * val["undervalued_20pct"].mean(), 3),
    "candidate_pool_size": len(pool),
    "recommended_pool_size": len(pool_rec),
    "needs_verification_count": len(needs_check),
    "anomaly_cap_pct": 100 * ANOMALY_CAP,
    "top20_raw_total_price_usd": float(top20_raw["price"].sum()),
    "top20_total_price_usd": float(top20["price"].sum()),
    "top20_total_predicted_usd": float(top20["predicted_price"].sum()),
    "top20_all_three_models_agree": int((top20["models_agree_undervalued"] == 3).sum()),
}
(OUT_T / "task4_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
