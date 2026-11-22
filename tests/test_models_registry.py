"""F04: cả ba trường hợp thắng đều cho đúng estimator, model_name và metrics thống nhất."""
import pytest
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from bds_valuation.models import (LR_NAME, MODEL_NAMES, RF_NAME, XGB_NAME, build_model, check_bundle_consistency,
                                  final_estimator, select_best)

EXPECTED = {LR_NAME: LinearRegression, RF_NAME: RandomForestRegressor, XGB_NAME: XGBRegressor}


@pytest.mark.parametrize("winner", MODEL_NAMES)
def test_winner_maps_to_same_estimator(winner):
    scores = {n: (5.0 if n == winner else 9.0) for n in MODEL_NAMES}
    chosen = select_best(scores)
    assert chosen == winner
    model = build_model(chosen, params={"max_depth": 3} if chosen == XGB_NAME else None)
    assert isinstance(final_estimator(model), EXPECTED[winner])
    check_bundle_consistency({"model": model, "model_name": chosen, "metrics_model_name": chosen})


def test_mismatched_bundle_is_rejected():
    with pytest.raises(AssertionError):
        check_bundle_consistency({"model": build_model(RF_NAME), "model_name": LR_NAME})
    with pytest.raises(AssertionError):
        check_bundle_consistency({"model": build_model(LR_NAME), "model_name": LR_NAME, "metrics_model_name": RF_NAME})


def test_unknown_model_name():
    with pytest.raises(KeyError):
        build_model("SVM")


def test_select_best_ignores_nan_and_unknown():
    assert select_best({LR_NAME: float("nan"), RF_NAME: 8.0, "Mốc thô": 1.0}) == RF_NAME


def test_tuned_params_applied_only_to_xgb():
    m = build_model(XGB_NAME, seed=3, params={"max_depth": 2, "n_estimators": 10})
    est = final_estimator(m)
    assert est.get_params()["max_depth"] == 2 and est.get_params()["random_state"] == 3
