"""Ames: tách điền thiếu học từ dữ liệu ra khỏi ETL và đưa vào Pipeline (F01).

``data/processed/ames_clean.csv`` phục vụ EDA nên đã điền trung vị theo neighborhood trên toàn bộ
dữ liệu. Khi mô hình hóa, các ô điền *học từ dữ liệu* (rule "Missing thực: trung vị..." và
"Năm gara ngoài miền...") được trả lại NaN theo ``metadata/imputation_audit.csv``; ``GroupMedianImputer``
học trung vị trên train (hoặc train của từng fold) và chỉ transform validation/test.
Các phép điền cấu trúc cố định (NA = không có tiện ích, gara không tồn tại = 0, nhãn "Unknown")
không học từ phân phối dữ liệu nên được giữ nguyên.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

LEARNED_RULE_PREFIXES = ("Missing thực: trung vị", "Năm gara ngoài miền")

AMES_DROP = {"source_row_id", "order", "pid", "sale_price", "price", "price_per_sqft", "price_iqr_outlier",
             "sale_type", "sale_condition", "distance_to_center_km", "distance_available", "raw_house_age",
             "has_any_imputation", "has_true_imputation", "sqft_living"}


def load_ames_for_modeling(clean_path, audit_path) -> tuple[pd.DataFrame, list[str]]:
    """Đọc Ames sạch rồi trả các ô điền học-từ-dữ-liệu về NaN. Trả về (frame, các cột đã khôi phục)."""
    ames = pd.read_csv(clean_path, keep_default_na=False, na_values=[""],
                       dtype={"pid": "string", "ms_subclass": "string"})
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    learned = audit[(audit["dataset"] == "ames") & audit["rule"].str.startswith(LEARNED_RULE_PREFIXES)]
    pos = pd.Series(ames.index, index=ames["source_row_id"].astype(int))
    restored = []
    for col, part in learned.groupby("column"):
        rows = pos.loc[part["source_row_id"].astype(int)].to_numpy()
        ames[col] = ames[col].astype(float)
        ames.loc[rows, col] = np.nan
        restored.append(col)
    return ames, sorted(restored)


def ames_feature_lists(ames: pd.DataFrame):
    drop = AMES_DROP | {c for c in ames if c.endswith("_imputed")}
    feats = [c for c in ames.columns if c not in drop]
    cats = [c for c in feats if not pd.api.types.is_numeric_dtype(ames[c])]
    nums = [c for c in feats if c not in cats]
    return feats, nums, cats


class GroupMedianImputer(BaseEstimator, TransformerMixin):
    """Điền NaN của cột số bằng trung vị theo nhóm (vd neighborhood) học trên dữ liệu fit;
    nhóm chưa gặp hoặc nhóm không có giá trị thì dùng trung vị toàn bộ dữ liệu fit.
    Cột nhóm được giữ nguyên (không biến đổi)."""

    def __init__(self, group_col="neighborhood", columns=None):
        self.group_col = group_col
        self.columns = columns

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        cols = self.columns if self.columns is not None else [
            c for c in X.columns if c != self.group_col and pd.api.types.is_numeric_dtype(X[c])]
        self.columns_ = list(cols)
        self.global_medians_ = X[self.columns_].median()
        self.group_medians_ = X.groupby(self.group_col)[self.columns_].median()
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        for c in self.columns_:
            miss = X[c].isna()
            if miss.any():
                by_group = X.loc[miss, self.group_col].map(self.group_medians_[c])
                X.loc[miss, c] = by_group.fillna(self.global_medians_[c]).to_numpy()
        return X

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.feature_names_in_, dtype=object)


def make_ames_model(kind: str, nums: list[str], cats: list[str], seed: int = 42):
    """Pipeline Ames: điền thiếu học trên train -> mã hóa -> mô hình trên log(price)."""
    from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
    from xgboost import XGBRegressor

    imp = GroupMedianImputer("neighborhood", columns=nums)
    if kind == "lr":
        pre = ColumnTransformer([("num", StandardScaler(), nums),
                                 ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), cats)])
        reg = LinearRegression()
    elif kind in ("rf", "xgb"):
        pre = ColumnTransformer([("num", "passthrough", nums),
                                 ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cats)])
        reg = (RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features=0.5, n_jobs=-1, random_state=seed)
               if kind == "rf" else
               XGBRegressor(n_estimators=1200, learning_rate=0.03, max_depth=4, min_child_weight=3, subsample=0.8,
                            colsample_bytree=0.5, tree_method="hist", n_jobs=-1, random_state=seed))
    else:
        raise KeyError(kind)
    return TransformedTargetRegressor(Pipeline([("imp", imp), ("pre", pre), ("model", reg)]),
                                      func=np.log, inverse_func=np.exp)
