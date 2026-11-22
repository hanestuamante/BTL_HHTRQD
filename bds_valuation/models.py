"""Một bảng ánh xạ tên mô hình -> hàm khởi tạo, dùng chung cho đánh giá, OOF và final fit (F04).

Trước đây nhánh OOF/final chỉ có XGBoost hoặc Random Forest, nên nếu Linear Regression thắng thì
tên/metrics ghi LR nhưng model lưu lại là RF. Nay mọi bước gọi ``build_model(name, ...)``.
"""
from __future__ import annotations

from typing import Callable, Mapping

import numpy as np
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler
from xgboost import XGBRegressor

from .features import CAT_FEATURES, LOG_COLS, NUM_FEATURES

SEED = 42
LR_NAME = "Linear Regression (baseline)"
RF_NAME = "Random Forest"
XGB_NAME = "XGBoost (tuned)"
MODEL_NAMES = (LR_NAME, RF_NAME, XGB_NAME)

XGB_DEFAULTS = dict(n_estimators=1500, learning_rate=0.03, max_depth=6, min_child_weight=3,
                    subsample=0.8, colsample_bytree=0.7, reg_lambda=1.0, tree_method="hist", n_jobs=-1)

XGB_SEARCH_SPACE = {
    "regressor__model__max_depth": [4, 5, 6, 7, 8],
    "regressor__model__learning_rate": [0.02, 0.03, 0.05],
    "regressor__model__n_estimators": [800, 1200, 1800],
    "regressor__model__min_child_weight": [1, 3, 5, 10],
    "regressor__model__subsample": [0.7, 0.8, 0.9],
    "regressor__model__colsample_bytree": [0.5, 0.7, 0.9],
    "regressor__model__reg_lambda": [0.5, 1.0, 3.0, 10.0],
}


def _log_target(pipe: Pipeline) -> TransformedTargetRegressor:
    # Học trên log(price) rồi đổi ngược về USD, nên MAPE/RMSE tính trên giá thật.
    return TransformedTargetRegressor(pipe, func=np.log, inverse_func=np.exp)


def make_linear(seed: int = SEED, params: Mapping | None = None):
    pre = ColumnTransformer([
        ("log", Pipeline([("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                          ("sc", StandardScaler())]), LOG_COLS),
        ("num", StandardScaler(), [c for c in NUM_FEATURES if c not in LOG_COLS]),
        ("zip", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
    ])
    return _log_target(Pipeline([("pre", pre), ("model", LinearRegression())]))


def tree_pre():
    return ColumnTransformer([
        ("num", "passthrough", NUM_FEATURES),
        ("zip", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT_FEATURES),
    ], verbose_feature_names_out=False)


def make_rf(seed: int = SEED, params: Mapping | None = None):
    kw = dict(n_estimators=300, min_samples_leaf=2, max_features=0.5, n_jobs=-1, random_state=seed)
    kw.update(params or {})
    return _log_target(Pipeline([("pre", tree_pre()), ("model", RandomForestRegressor(**kw))]))


def make_xgb(seed: int = SEED, params: Mapping | None = None):
    kw = {**XGB_DEFAULTS, "random_state": seed}
    kw.update(params or {})
    return _log_target(Pipeline([("pre", tree_pre()), ("model", XGBRegressor(**kw))]))


MODEL_REGISTRY: dict[str, Callable] = {LR_NAME: make_linear, RF_NAME: make_rf, XGB_NAME: make_xgb}
ESTIMATOR_TYPES = {LR_NAME: LinearRegression, RF_NAME: RandomForestRegressor, XGB_NAME: XGBRegressor}


def build_model(name: str, seed: int = SEED, params: Mapping | None = None):
    """Khởi tạo mô hình theo tên. ``params`` chỉ áp cho mô hình có siêu tham số đã tinh chỉnh."""
    if name not in MODEL_REGISTRY:
        raise KeyError(f"Mô hình không có trong registry: {name!r}. Hợp lệ: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[name](seed=seed, params=params)


def params_for(name: str, tuned: Mapping[str, Mapping] | None) -> Mapping | None:
    return (tuned or {}).get(name)


def select_best(scores: Mapping[str, float]) -> str:
    """Chọn mô hình có điểm lỗi (MAPE) nhỏ nhất. Điểm phải đến từ CV/validation, không từ tập test cuối."""
    valid = {k: v for k, v in scores.items() if k in MODEL_REGISTRY and np.isfinite(v)}
    if not valid:
        raise ValueError("Không có điểm hợp lệ để chọn mô hình.")
    return min(valid, key=valid.get)


def final_estimator(model):
    """Lấy estimator lõi (LinearRegression/RandomForest/XGB) bên trong TransformedTargetRegressor."""
    reg = getattr(model, "regressor_", None) or model.regressor
    return reg.named_steps["model"]


def check_bundle_consistency(bundle: Mapping) -> None:
    """Tên mô hình, kiểu estimator và metrics gắn kèm phải thống nhất."""
    name = bundle["model_name"]
    expected = ESTIMATOR_TYPES[name]
    est = final_estimator(bundle["model"])
    if not isinstance(est, expected):
        raise AssertionError(f"Bundle ghi {name!r} nhưng estimator là {type(est).__name__}")
    if bundle.get("metrics_model_name", name) != name:
        raise AssertionError("Metrics trong bundle thuộc mô hình khác với model_name")
