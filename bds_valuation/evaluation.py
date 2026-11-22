"""Thước đo, chia tập, chọn mô hình bằng CV, backtest thời gian độc lập (F02) và nested CV (F03)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, RandomizedSearchCV

from .models import MODEL_NAMES, SEED, XGB_NAME, XGB_SEARCH_SPACE, build_model, select_best


def metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
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


def mape(y_true, y_pred) -> float:
    return 100 * mean_absolute_percentage_error(y_true, y_pred)


def group_split(X, y, groups, test_size=0.2, seed=SEED):
    """Chia train/test theo id tài sản: một căn bán nhiều lần chỉ nằm ở một phía."""
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed).split(X, y, groups))
    assert not set(np.asarray(groups)[tr]) & set(np.asarray(groups)[te])
    return tr, te


def tune_xgb(X, y, cv, groups=None, n_iter=20, seed=SEED):
    """RandomizedSearch cho XGBoost. ``cv`` là bộ chia CHỈ trên dữ liệu được truyền vào."""
    search = RandomizedSearchCV(build_model(XGB_NAME, seed=seed), XGB_SEARCH_SPACE, n_iter=n_iter, cv=cv,
                                scoring="neg_mean_absolute_percentage_error", random_state=seed,
                                n_jobs=1, refit=False)
    search.fit(X, y, groups=groups)
    best = {k.replace("regressor__model__", ""): v for k, v in search.best_params_.items()}
    return best, search


def cv_mape(name, X, y, splits, params=None, seed=SEED) -> float:
    """MAPE trung bình theo các cặp (train_idx, val_idx) cho trước."""
    scores = []
    for a, b in splits:
        m = build_model(name, seed=seed, params=params).fit(X.iloc[a], y.iloc[a])
        scores.append(mape(y.iloc[b], m.predict(X.iloc[b])))
    return float(np.mean(scores))


def select_by_cv(X, y, splits, tuned_params: Mapping[str, Mapping], seed=SEED) -> tuple[str, dict]:
    """Chọn mô hình bằng CV trên dữ liệu được phép dùng; tập đánh giá cuối không tham gia."""
    scores = {n: cv_mape(n, X, y, splits, params=tuned_params.get(n), seed=seed) for n in MODEL_NAMES}
    return select_best(scores), scores


# ---------------- F02: backtest theo thời gian độc lập ----------------
@dataclass
class TemporalSplit:
    cutoff: pd.Timestamp
    val_start: pd.Timestamp
    past_idx: np.ndarray            # mọi dòng trước cutoff (dùng để tinh chỉnh + fit cuối)
    inner_train_idx: np.ndarray     # quá khứ trước val_start (fit khi tinh chỉnh)
    inner_val_idx: np.ndarray       # quá khứ trong [val_start, cutoff) (chấm điểm khi tinh chỉnh)
    future_idx: np.ndarray          # sau cutoff, chỉ tài sản chưa xuất hiện trong quá khứ
    info: dict = field(default_factory=dict)


def temporal_split(dates, groups, cutoff="2015-02-01", val_months=3) -> TemporalSplit:
    """Tách tập tương lai TRƯỚC; tinh chỉnh chỉ dùng quá khứ với validation theo thời gian."""
    dates = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    groups = pd.Series(np.asarray(groups)).reset_index(drop=True)
    cutoff = pd.Timestamp(cutoff)
    val_start = cutoff - pd.DateOffset(months=val_months)
    past = (dates < cutoff).to_numpy()
    past_ids = set(groups[past])
    future = (~past) & ~groups.isin(past_ids).to_numpy()
    inner_tr = (dates < val_start).to_numpy()
    inner_val = past & ~inner_tr & ~groups.isin(set(groups[inner_tr])).to_numpy()
    s = TemporalSplit(cutoff, val_start, np.flatnonzero(past), np.flatnonzero(inner_tr),
                      np.flatnonzero(inner_val), np.flatnonzero(future))
    assert dates.iloc[s.past_idx].max() < cutoff <= dates.iloc[s.future_idx].min()
    assert not set(s.past_idx) & set(s.future_idx)
    assert not set(groups.iloc[s.future_idx]) & past_ids
    s.info = {
        "cutoff": str(cutoff.date()), "validation_start": str(val_start.date()),
        "past_rows": len(s.past_idx), "inner_train_rows": len(s.inner_train_idx),
        "inner_validation_rows": len(s.inner_val_idx), "future_rows": len(s.future_idx),
        "future_rows_dropped_seen_property": int(((~past) & ~future).sum()),
        "past_date_range": [str(dates.iloc[s.past_idx].min().date()), str(dates.iloc[s.past_idx].max().date())],
        "future_date_range": [str(dates.iloc[s.future_idx].min().date()), str(dates.iloc[s.future_idx].max().date())],
    }
    return s


def run_temporal_backtest(X, y, dates, groups, cutoff="2015-02-01", n_iter=20, seed=SEED):
    """Tinh chỉnh + chọn mô hình chỉ trên quá khứ, khóa cấu hình, rồi chấm tương lai đúng một lần."""
    s = temporal_split(dates, groups, cutoff)
    Xp, yp = X.iloc[s.past_idx].reset_index(drop=True), y.iloc[s.past_idx].reset_index(drop=True)
    pos = {v: i for i, v in enumerate(s.past_idx)}
    inner = [(np.array([pos[i] for i in s.inner_train_idx]), np.array([pos[i] for i in s.inner_val_idx]))]
    best_xgb, _ = tune_xgb(Xp, yp, cv=inner, n_iter=n_iter, seed=seed)
    tuned = {XGB_NAME: best_xgb}
    chosen, val_scores = select_by_cv(Xp, yp, inner, tuned, seed=seed)
    locked = {"model": chosen, "params": tuned.get(chosen)}
    rows = []
    for name in dict.fromkeys([MODEL_NAMES[0], chosen]):        # baseline + mô hình đã khóa
        m = build_model(name, seed=seed, params=tuned.get(name)).fit(Xp, yp)
        rows.append({"Thi_truong": "King County (backtest thời gian)", "Mo_hinh": name,
                     **metrics(y.iloc[s.future_idx], m.predict(X.iloc[s.future_idx])),
                     "Thoi_gian_fit_s": np.nan, "Chon_truoc_khi_xem_tuong_lai": name == chosen})
    info = {**s.info, "xgb_params_tuned_on_past": best_xgb, "validation_mape_by_model": val_scores,
            "locked_model": locked, "rule": "Tương lai tách trước; tinh chỉnh và chọn mô hình chỉ dùng quá khứ "
                                              "(train < validation_start, validation = 3 tháng cuối quá khứ)."}
    return pd.DataFrame(rows), info


# ---------------- F03: nested CV cho ước lượng hiệu năng nghiêm ngặt ----------------
def nested_cv_oof(X, y, groups, outer_splits=5, inner_splits=3, n_iter=10, seed=SEED, log=print):
    """Mỗi outer fold: tinh chỉnh XGBoost + chọn mô hình CHỈ trong outer-train (GroupKFold theo id),
    rồi dự báo outer-test. Trả về dự báo OOF và bảng chi tiết từng fold."""
    oof = np.full(len(X), np.nan)
    rows = []
    outer = GroupKFold(n_splits=outer_splits, shuffle=True, random_state=seed)
    for k, (a, b) in enumerate(outer.split(X, y, groups)):
        t0 = time.time()
        Xa, ya, ga = X.iloc[a].reset_index(drop=True), y.iloc[a].reset_index(drop=True), groups.iloc[a].reset_index(drop=True)
        assert not set(ga) & set(groups.iloc[b])
        inner = list(GroupKFold(n_splits=inner_splits, shuffle=True, random_state=seed).split(Xa, ya, ga))
        best_xgb, search = tune_xgb(Xa, ya, cv=inner, n_iter=n_iter, seed=seed)
        scores = {XGB_NAME: -100 * search.best_score_}
        for n in MODEL_NAMES:
            if n != XGB_NAME:
                scores[n] = cv_mape(n, Xa, ya, inner, seed=seed)
        chosen = select_best(scores)
        m = build_model(chosen, seed=seed, params=best_xgb if chosen == XGB_NAME else None).fit(Xa, ya)
        oof[b] = m.predict(X.iloc[b])
        rows.append({"outer_fold": k + 1, "train_rows": len(a), "test_rows": len(b), "chosen_model": chosen,
                     **{f"inner_MAPE_{n}": v for n, v in scores.items()}, "xgb_params": best_xgb,
                     "outer_test_MAPE_%": mape(y.iloc[b], oof[b]), "seconds": round(time.time() - t0, 1)})
        log(f"  nested fold {k+1}/{outer_splits}: chọn {chosen}, outer MAPE {rows[-1]['outer_test_MAPE_%']:.2f}% "
            f"({rows[-1]['seconds']}s)")
    assert not np.isnan(oof).any()
    return oof, pd.DataFrame(rows)


def oof_predict(name, X, y, groups, seed=SEED, n_splits=5, params=None):
    """Dự báo out-of-fold với cấu hình cố định (dùng cho sàng lọc; xem giới hạn F03 trong báo cáo)."""
    oof = np.zeros(len(X))
    for a, b in GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y, groups):
        oof[b] = build_model(name, seed=seed, params=params).fit(X.iloc[a], y.iloc[a]).predict(X.iloc[b])
    return oof
