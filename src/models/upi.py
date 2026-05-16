"""UPI-enhanced credit risk model.

This module is intentionally separate from the existing FULL and REDUCED
training pipeline. It trains, persists, loads, and scores a third model tier
from the merged Home Credit + UPI dataset without replacing any current
runtime artifacts.
"""

from __future__ import annotations

import json
import os
import sys
import argparse
from dataclasses import dataclass, field
from typing import Any

if __package__ is None or __package__ == "":
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from configs.config import APPROVE_THRESHOLD, ARTIFACT_DIR, DECLINE_THRESHOLD, RANDOM_STATE
from src.models.runtime_support import LogisticProbabilityCalibrator, TreeShapExplainer
from src.runtime_verification import dataframe_fingerprint

if __name__ == "__main__":
    # Keep persisted builders importable when this file is executed via
    # `python -m src.models.upi`.
    sys.modules["src.models.upi"] = sys.modules[__name__]

UPI_DATASET_PATH = os.path.join("data", "raw", "final_base_with_upi_corrected.csv")
UPI_MODEL_VERSION = "upi_v1.1.0"
UPI_REPORT_FILENAME = "upi_training_report.json"
UPI_BUILDER_FILENAME = "upi_feature_builder.joblib"
UPI_MODEL_FILENAME = "upi_model.joblib"
UPI_CALIBRATOR_FILENAME = "upi_calibrator.joblib"
UPI_EXPLAINER_FILENAME = "upi_shap_explainer.joblib"
TARGET_COLUMN = "TARGET"
ID_COLUMNS = ("SK_ID_CURR", "SK_ID_PREV")
EMPTY_SOURCE_COLUMNS = (
    "AMT_PAYMENT",
    "AMT_INSTALMENT",
    "AMT_BALANCE",
    "AMT_CREDIT_LIMIT_ACTUAL",
    "CNT_INSTALMENT",
    "CNT_INSTALMENT_FUTURE",
)
RENAME_COLUMNS = {
    "AMT_CREDIT_x": "AMT_CREDIT_CURRENT",
    "AMT_CREDIT_y": "AMT_CREDIT_PREVIOUS",
}
KNOWN_CATEGORICAL_COLUMNS = (
    "NAME_CONTRACT_TYPE",
    "CODE_GENDER",
    "FLAG_OWN_CAR",
    "FLAG_OWN_REALTY",
    "NAME_TYPE_SUITE",
    "NAME_INCOME_TYPE",
    "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS",
    "NAME_HOUSING_TYPE",
    "OCCUPATION_TYPE",
    "WEEKDAY_APPR_PROCESS_START",
    "ORGANIZATION_TYPE",
    "FONDKAPREMONT_MODE",
    "HOUSETYPE_MODE",
    "WALLSMATERIAL_MODE",
    "EMERGENCYSTATE_MODE",
)
UPI_TRANSACTION_COLUMNS = (
    "balance_instability_score",
    "failed_due_to_low_balance",
    "failed_txn_count",
    "outflow_volatility",
    "inflow_volatility",
    "txn_value_std",
    "monthly_inflow",
    "monthly_outflow",
    "success_txn_count",
    "monthly_txn_count",
    "avg_txn_value",
    "median_txn_value",
    "inflow_txn_count",
    "outflow_txn_count",
    "weekday_txn_ratio",
    "weekend_txn_ratio",
    "distinct_counterparties",
    "active_days",
    "peak_txn_day_count",
)
UPI_HIGH_RISK_PROXY_COLUMNS = (
    "balance_instability_score",
    "failed_due_to_low_balance",
    "failed_txn_count",
    "outflow_volatility",
    "inflow_volatility",
    "txn_value_std",
    "success_txn_count",
    "peak_txn_day_count",
)
UPI_STABLE_TRANSACTION_COLUMNS = (
    "monthly_inflow",
    "monthly_outflow",
    "monthly_txn_count",
    "avg_txn_value",
    "median_txn_value",
    "inflow_txn_count",
    "outflow_txn_count",
    "weekday_txn_ratio",
    "weekend_txn_ratio",
    "distinct_counterparties",
    "active_days",
)
ENGINEERED_UPI_COLUMNS = (
    "AGE_YEARS",
    "EMPLOYED_YEARS",
    "CREDIT_INCOME_RATIO",
    "ANNUITY_INCOME_RATIO",
    "GOODS_CREDIT_RATIO",
    "PREVIOUS_CREDIT_INCOME_RATIO",
    "BUREAU_DEBT_CREDIT_RATIO",
    "UPI_NET_MONTHLY_CASHFLOW",
    "UPI_OUTFLOW_INFLOW_RATIO",
    "UPI_FAILED_TXN_RATIO",
    "UPI_SUCCESS_TXN_RATIO",
    "UPI_LOW_BALANCE_FAILED_RATIO",
    "UPI_COUNTERPARTY_DIVERSITY",
    "UPI_ACTIVE_DAY_RATIO",
    "UPI_VOLATILITY_MEAN",
    "UPI_LIQUIDITY_PRESSURE_SCORE",
    "UPI_CASHFLOW_STABILITY_SCORE",
    "EXT_SOURCE_MEAN",
    "EXT_SOURCE_STD",
    "EXT_SOURCE_MIN",
    "EXT_SOURCE_MAX",
    "EXT_SOURCE_RANGE",
    "DAYS_EMPLOYED_ANOM",
)


@dataclass
class UpiFeatureBuilder:
    """Frozen transformer for the UPI model tier."""

    raw_columns_: list[str] = field(default_factory=list)
    excluded_raw_columns_: list[str] = field(default_factory=list)
    pre_model_columns_: list[str] = field(default_factory=list)
    encoded_columns_: list[str] = field(default_factory=list)
    categorical_columns_: list[str] = field(default_factory=list)
    categorical_fill_values_: dict[str, str] = field(default_factory=dict)
    rare_category_maps_: dict[str, set[str]] = field(default_factory=dict)
    missing_flag_columns_: list[str] = field(default_factory=list)
    numeric_imputers_: dict[str, float] = field(default_factory=dict)
    numeric_scale_columns_: list[str] = field(default_factory=list)
    scaler_: StandardScaler | None = None
    fit_row_count_: int = 0
    dataset_fingerprint_: str = ""
    model_version_: str = UPI_MODEL_VERSION

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = f"{path}.tmp"
        joblib.dump(self, tmp_path)
        os.replace(tmp_path, path)

    def transform(self, df: pd.DataFrame, *, scaled: bool = False) -> pd.DataFrame:
        pre_model = _build_upi_pre_model_frame(df, raw_columns=self.raw_columns_)
        pre_model = _align_columns(pre_model, self.pre_model_columns_)
        pre_model = _apply_rare_category_maps(
            pre_model,
            self.categorical_columns_,
            self.categorical_fill_values_,
            self.rare_category_maps_,
        )
        pre_model = _create_missing_flag_columns(pre_model, self.missing_flag_columns_)
        pre_model = _fill_numeric_columns(pre_model, self.numeric_imputers_)
        encoded = _encode_to_columns(pre_model, self.categorical_columns_, self.encoded_columns_)
        if scaled:
            encoded = _scale_numeric_columns(encoded, self)
        return encoded


UpiFeatureBuilder.__module__ = "src.models.upi"


def train_upi_model(
    dataset_path: str = UPI_DATASET_PATH,
    artifact_dir: str = ARTIFACT_DIR,
    *,
    sample_rows: int | None = None,
) -> dict[str, Any]:
    """Train and persist the standalone UPI model.

    The split is stratified and mirrors the existing project convention:
    train 60%, validation-model 10%, validation-policy 10%, test 20%.
    """

    os.makedirs(artifact_dir, exist_ok=True)
    bundle = _load_upi_bundle(dataset_path, sample_rows=sample_rows)
    builder = fit_upi_builder(
        bundle["train"],
        save_path=os.path.join(artifact_dir, UPI_BUILDER_FILENAME),
    )

    train_X = build_upi(bundle["train"], builder)
    val_model_X = build_upi(bundle["val_model"], builder)
    val_policy_X = build_upi(bundle["val_policy"], builder)
    test_X = build_upi(bundle["test"], builder)
    y_train = bundle["train"][TARGET_COLUMN].to_numpy(dtype=int)
    y_val_model = bundle["val_model"][TARGET_COLUMN].to_numpy(dtype=int)
    y_val_policy = bundle["val_policy"][TARGET_COLUMN].to_numpy(dtype=int)
    y_test = bundle["test"][TARGET_COLUMN].to_numpy(dtype=int)

    result = _train_xgboost_upi(
        train_X,
        y_train,
        val_model_X,
        y_val_model,
        val_policy_X,
        y_val_policy,
        test_X,
        y_test,
    )

    model_path = os.path.join(artifact_dir, UPI_MODEL_FILENAME)
    calibrator_path = os.path.join(artifact_dir, UPI_CALIBRATOR_FILENAME)
    explainer_path = os.path.join(artifact_dir, UPI_EXPLAINER_FILENAME)
    joblib.dump(result["model"], model_path)
    joblib.dump(result["calibrator"], calibrator_path)
    joblib.dump(TreeShapExplainer(result["model"]), explainer_path)

    report = {
        "model_version": UPI_MODEL_VERSION,
        "model_family": "xgboost",
        "dataset_path": os.path.abspath(dataset_path),
        "dataset_fingerprint": builder.dataset_fingerprint_,
        "target": TARGET_COLUMN,
        "class_balance": _class_balance(bundle["train"][TARGET_COLUMN]),
        "sample_counts": {
            split_name: int(len(frame)) for split_name, frame in bundle.items()
        },
        "feature_count": int(len(builder.encoded_columns_)),
        "raw_feature_count": int(len(builder.raw_columns_)),
        "feature_scope": "upi_transaction_stable_api_fields",
        "upi_transaction_columns": [c for c in UPI_TRANSACTION_COLUMNS if c in builder.raw_columns_],
        "excluded_upi_transaction_columns": builder.excluded_raw_columns_,
        "excluded_upi_transaction_reason": (
            "Excluded from default training because these generated transaction features have "
            "implausibly high standalone target separation in the supplied synthetic UPI file "
            "or are direct derivatives of failed/instability behavior."
        ),
        "engineered_feature_columns": list(ENGINEERED_UPI_COLUMNS),
        "selected_candidate": result["selected_candidate"],
        "selected_params": result["selected_params"],
        "selection": {
            "val_model_roc_auc": result["val_model_roc_auc"],
            "val_model_auc_pr": result["val_model_auc_pr"],
            "calibrator": result["selected_calibrator"],
            "val_policy_calibration_metrics": result["val_policy_calibration_metrics"],
        },
        "metrics": result["metrics"],
        "artifacts": {
            "builder": os.path.join(artifact_dir, UPI_BUILDER_FILENAME),
            "model": model_path,
            "calibrator": calibrator_path,
            "explainer": explainer_path,
            "report": os.path.join(artifact_dir, UPI_REPORT_FILENAME),
        },
        "notes": [
            "This UPI model is standalone and does not overwrite FULL or REDUCED artifacts.",
            "UPI training is restricted to the same stable transaction fields available to the UPI API tier.",
            "High-risk target-proxy UPI fields are excluded by default instead of being used to inflate AUC.",
            "DAYS_EMPLOYED=365243 is converted to DAYS_EMPLOYED_ANOM=1 and excluded as a real duration.",
            "Known empty source columns are dropped before modeling.",
            "Class imbalance is handled with XGBoost scale_pos_weight; AUC-ROC and AUC-PR are reported.",
        ],
    }
    _write_json(os.path.join(artifact_dir, UPI_REPORT_FILENAME), report)
    return report


def fit_upi_builder(train_df: pd.DataFrame, save_path: str | None = None) -> UpiFeatureBuilder:
    raw_columns = _select_upi_raw_columns(train_df)
    excluded_columns = _select_excluded_upi_raw_columns(train_df, raw_columns)
    pre_model = _build_upi_pre_model_frame(train_df, raw_columns=raw_columns)
    pre_model = pre_model.loc[:, pre_model.notna().any(axis=0)]
    categorical_cols = [c for c in KNOWN_CATEGORICAL_COLUMNS if c in pre_model.columns]
    categorical_fill_values = {col: "Unknown" for col in categorical_cols}
    rare_maps = _fit_rare_category_maps(pre_model, categorical_cols)
    prepared = _apply_rare_category_maps(
        pre_model,
        categorical_cols,
        categorical_fill_values,
        rare_maps,
    )
    missing_flags = _fit_missing_flag_columns(prepared)
    prepared = _create_missing_flag_columns(prepared, missing_flags)
    numeric_cols = [
        c
        for c in prepared.select_dtypes(include=[np.number]).columns
        if not c.endswith("_IS_MISSING") and prepared[c].notna().any()
    ]
    numeric_imputers = _fit_numeric_imputers(prepared, numeric_cols)
    prepared = _fill_numeric_columns(prepared, numeric_imputers)
    encoded = pd.get_dummies(prepared, columns=categorical_cols, dtype=float, drop_first=False)
    scaler = StandardScaler(with_mean=False) if numeric_cols else None
    if scaler is not None:
        scaler.fit(encoded[numeric_cols])

    builder = UpiFeatureBuilder(
        raw_columns_=raw_columns,
        excluded_raw_columns_=excluded_columns,
        pre_model_columns_=pre_model.columns.tolist(),
        encoded_columns_=encoded.columns.tolist(),
        categorical_columns_=categorical_cols,
        categorical_fill_values_=categorical_fill_values,
        rare_category_maps_=rare_maps,
        missing_flag_columns_=missing_flags,
        numeric_imputers_=numeric_imputers,
        numeric_scale_columns_=numeric_cols,
        scaler_=scaler,
        fit_row_count_=int(len(train_df)),
        dataset_fingerprint_=dataframe_fingerprint(train_df),
    )
    if save_path is not None:
        builder.save(save_path)
    return builder


def build_upi(df: pd.DataFrame, builder: UpiFeatureBuilder, *, scaled: bool = False) -> pd.DataFrame:
    if not isinstance(builder, UpiFeatureBuilder):
        raise TypeError("builder must be a UpiFeatureBuilder instance")
    return builder.transform(df, scaled=scaled)


def load_upi_artifacts(artifact_dir: str = ARTIFACT_DIR) -> dict[str, Any]:
    setattr(sys.modules["__main__"], "UpiFeatureBuilder", UpiFeatureBuilder)
    return {
        "builder": joblib.load(os.path.join(artifact_dir, UPI_BUILDER_FILENAME)),
        "model": joblib.load(os.path.join(artifact_dir, UPI_MODEL_FILENAME)),
        "calibrator": joblib.load(os.path.join(artifact_dir, UPI_CALIBRATOR_FILENAME)),
        "explainer": joblib.load(os.path.join(artifact_dir, UPI_EXPLAINER_FILENAME)),
        "report": _load_optional_json(os.path.join(artifact_dir, UPI_REPORT_FILENAME)),
    }


def score_upi_frame(df: pd.DataFrame, artifact_dir: str = ARTIFACT_DIR) -> pd.DataFrame:
    """Score one or more UPI rows and return probabilities plus decisions."""

    artifacts = load_upi_artifacts(artifact_dir)
    features = build_upi(df, artifacts["builder"])
    raw_pd = np.asarray(artifacts["model"].predict_proba(features), dtype=float)[:, 1]
    calibrated_pd = np.asarray(artifacts["calibrator"].predict(raw_pd), dtype=float)
    calibrated_pd = np.clip(calibrated_pd, 0.0, 1.0)
    return pd.DataFrame(
        {
            "probability_of_default": calibrated_pd,
            "decision": [_decision_from_pd(prob) for prob in calibrated_pd],
        },
        index=df.index,
    )


def score_upi_record(record: dict[str, Any], artifact_dir: str = ARTIFACT_DIR) -> dict[str, Any]:
    scored = score_upi_frame(pd.DataFrame([record]), artifact_dir=artifact_dir).iloc[0]
    return {
        "probability_of_default": float(scored["probability_of_default"]),
        "decision": str(scored["decision"]),
        "coverage_tier": "UPI",
        "model_version": UPI_MODEL_VERSION,
    }


def _load_upi_bundle(dataset_path: str, *, sample_rows: int | None = None) -> dict[str, pd.DataFrame]:
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"UPI dataset not found: {dataset_path}")
    read_kwargs = {"nrows": sample_rows} if sample_rows is not None else {}
    df = pd.read_csv(dataset_path, **read_kwargs)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"{TARGET_COLUMN} column is required in the UPI dataset")
    df = df[df[TARGET_COLUMN].notna()].copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    if df[TARGET_COLUMN].nunique() != 2:
        raise ValueError("UPI dataset must contain both TARGET classes")
    train_df, temp_df = train_test_split(
        df,
        test_size=0.40,
        random_state=RANDOM_STATE,
        stratify=df[TARGET_COLUMN],
    )
    val_model_df, temp_df = train_test_split(
        temp_df,
        test_size=0.75,
        random_state=RANDOM_STATE,
        stratify=temp_df[TARGET_COLUMN],
    )
    val_policy_df, test_df = train_test_split(
        temp_df,
        test_size=(2.0 / 3.0),
        random_state=RANDOM_STATE,
        stratify=temp_df[TARGET_COLUMN],
    )
    return {
        "train": train_df.reset_index(drop=True),
        "val_model": val_model_df.reset_index(drop=True),
        "val_policy": val_policy_df.reset_index(drop=True),
        "test": test_df.reset_index(drop=True),
    }


def _select_upi_raw_columns(df: pd.DataFrame) -> list[str]:
    blocked = {TARGET_COLUMN, *ID_COLUMNS, *EMPTY_SOURCE_COLUMNS, *UPI_HIGH_RISK_PROXY_COLUMNS}
    return [c for c in UPI_STABLE_TRANSACTION_COLUMNS if c in df.columns and c not in blocked]


def _select_excluded_upi_raw_columns(df: pd.DataFrame, selected_columns: list[str]) -> list[str]:
    selected = set(selected_columns)
    excluded = [
        c
        for c in UPI_TRANSACTION_COLUMNS
        if c in df.columns and c not in selected
    ]
    return sorted(excluded)


def _build_upi_pre_model_frame(
    df: pd.DataFrame,
    *,
    raw_columns: list[str] | None = None,
) -> pd.DataFrame:
    selected = list(raw_columns) if raw_columns is not None else _select_upi_raw_columns(df)
    work = df.copy()
    for col in selected:
        if col not in work.columns:
            work[col] = np.nan
    work = work[selected].rename(columns=RENAME_COLUMNS)
    work = _normalize_categorical_values(work)
    work = _coerce_known_numeric_columns(work)
    work = _apply_days_employed_fix(work)
    work = _engineer_upi_features(work)
    return work


def _normalize_categorical_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.select_dtypes(include=["object", "category"]).columns:
        df[col] = df[col].replace({"XNA": "Unknown", "": "Unknown"}).fillna("Unknown")
    return df


def _coerce_known_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col in KNOWN_CATEGORICAL_COLUMNS:
            continue
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _apply_days_employed_fix(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "DAYS_EMPLOYED" not in df.columns:
        df["DAYS_EMPLOYED"] = np.nan
    employed = pd.to_numeric(df["DAYS_EMPLOYED"], errors="coerce")
    anomalous = employed.eq(365243)
    df["DAYS_EMPLOYED_ANOM"] = anomalous.astype("int8")
    df["DAYS_EMPLOYED"] = employed.mask(anomalous, np.nan)
    return df


def _engineer_upi_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in [
        "DAYS_BIRTH",
        "DAYS_EMPLOYED",
        "AMT_INCOME_TOTAL",
        "AMT_CREDIT_CURRENT",
        "AMT_CREDIT_PREVIOUS",
        "AMT_ANNUITY",
        "AMT_GOODS_PRICE",
        "AMT_CREDIT_SUM",
        "AMT_CREDIT_SUM_DEBT",
        "monthly_inflow",
        "monthly_outflow",
        "monthly_txn_count",
        "success_txn_count",
        "failed_txn_count",
        "failed_due_to_low_balance",
        "distinct_counterparties",
        "active_days",
        "balance_instability_score",
        "inflow_volatility",
        "outflow_volatility",
        "txn_value_std",
    ]:
        if col not in df.columns:
            df[col] = np.nan

    df["AGE_YEARS"] = -pd.to_numeric(df["DAYS_BIRTH"], errors="coerce") / 365.25
    df["EMPLOYED_YEARS"] = -pd.to_numeric(df["DAYS_EMPLOYED"], errors="coerce") / 365.25
    income = pd.to_numeric(df["AMT_INCOME_TOTAL"], errors="coerce")
    current_credit = pd.to_numeric(df["AMT_CREDIT_CURRENT"], errors="coerce")
    previous_credit = pd.to_numeric(df["AMT_CREDIT_PREVIOUS"], errors="coerce")
    monthly_inflow = pd.to_numeric(df["monthly_inflow"], errors="coerce")
    monthly_outflow = pd.to_numeric(df["monthly_outflow"], errors="coerce")
    monthly_txn = pd.to_numeric(df["monthly_txn_count"], errors="coerce")
    failed_txn = pd.to_numeric(df["failed_txn_count"], errors="coerce")

    df["CREDIT_INCOME_RATIO"] = _safe_div(current_credit, income)
    df["ANNUITY_INCOME_RATIO"] = _safe_div(pd.to_numeric(df["AMT_ANNUITY"], errors="coerce"), income)
    df["GOODS_CREDIT_RATIO"] = _safe_div(pd.to_numeric(df["AMT_GOODS_PRICE"], errors="coerce"), current_credit)
    df["PREVIOUS_CREDIT_INCOME_RATIO"] = _safe_div(previous_credit, income)
    df["BUREAU_DEBT_CREDIT_RATIO"] = _safe_div(
        pd.to_numeric(df["AMT_CREDIT_SUM_DEBT"], errors="coerce"),
        pd.to_numeric(df["AMT_CREDIT_SUM"], errors="coerce"),
    )
    df["UPI_NET_MONTHLY_CASHFLOW"] = monthly_inflow - monthly_outflow
    df["UPI_OUTFLOW_INFLOW_RATIO"] = _safe_div(monthly_outflow, monthly_inflow)
    df["UPI_FAILED_TXN_RATIO"] = _safe_div(failed_txn, monthly_txn)
    df["UPI_SUCCESS_TXN_RATIO"] = _safe_div(pd.to_numeric(df["success_txn_count"], errors="coerce"), monthly_txn)
    df["UPI_LOW_BALANCE_FAILED_RATIO"] = _safe_div(
        pd.to_numeric(df["failed_due_to_low_balance"], errors="coerce"),
        failed_txn,
    )
    df["UPI_COUNTERPARTY_DIVERSITY"] = _safe_div(
        pd.to_numeric(df["distinct_counterparties"], errors="coerce"),
        monthly_txn,
    )
    df["UPI_ACTIVE_DAY_RATIO"] = _safe_div(pd.to_numeric(df["active_days"], errors="coerce"), 30.0)
    volatility_cols = ["inflow_volatility", "outflow_volatility", "txn_value_std"]
    volatility_frame = df[volatility_cols]
    if volatility_frame.notna().any(axis=None):
        df["UPI_VOLATILITY_MEAN"] = volatility_frame.mean(axis=1)
    else:
        df["UPI_VOLATILITY_MEAN"] = np.nan
    df["UPI_LIQUIDITY_PRESSURE_SCORE"] = (
        pd.to_numeric(df["balance_instability_score"], errors="coerce").fillna(0.0)
        + df["UPI_FAILED_TXN_RATIO"].fillna(0.0)
        + df["UPI_LOW_BALANCE_FAILED_RATIO"].fillna(0.0)
        + df["UPI_OUTFLOW_INFLOW_RATIO"].fillna(0.0)
    )
    df["UPI_CASHFLOW_STABILITY_SCORE"] = _safe_div(
        monthly_inflow - monthly_outflow,
        1.0 + df["UPI_VOLATILITY_MEAN"].abs(),
    )
    ext_cols = [c for c in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"] if c in df.columns]
    if ext_cols:
        df["EXT_SOURCE_MEAN"] = df[ext_cols].mean(axis=1)
        df["EXT_SOURCE_STD"] = df[ext_cols].std(axis=1)
        df["EXT_SOURCE_MIN"] = df[ext_cols].min(axis=1)
        df["EXT_SOURCE_MAX"] = df[ext_cols].max(axis=1)
        df["EXT_SOURCE_RANGE"] = df["EXT_SOURCE_MAX"] - df["EXT_SOURCE_MIN"]
    return df


def _train_xgboost_upi(
    train_X: pd.DataFrame,
    train_y: np.ndarray,
    val_model_X: pd.DataFrame,
    val_model_y: np.ndarray,
    val_policy_X: pd.DataFrame,
    val_policy_y: np.ndarray,
    test_X: pd.DataFrame,
    test_y: np.ndarray,
) -> dict[str, Any]:
    pos = int(train_y.sum())
    neg = int(len(train_y) - pos)
    scale_pos_weight = float(neg / max(pos, 1))
    candidates = [
        (
            "conservative_stable_upi",
            {
                "n_estimators": 160,
                "max_depth": 2,
                "learning_rate": 0.025,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_lambda": 10.0,
                "min_child_weight": 25.0,
                "scale_pos_weight": scale_pos_weight,
            },
        ),
        (
            "regularized_stable_upi",
            {
                "n_estimators": 220,
                "max_depth": 3,
                "learning_rate": 0.03,
                "subsample": 0.8,
                "colsample_bytree": 0.75,
                "reg_lambda": 12.0,
                "min_child_weight": 30.0,
                "scale_pos_weight": scale_pos_weight,
            },
        ),
    ]
    best_model: XGBClassifier | None = None
    best_name = ""
    best_params: dict[str, Any] = {}
    best_auc = float("-inf")
    best_auc_pr = float("-inf")

    for candidate_name, params in candidates:
        model = XGBClassifier(
            random_state=RANDOM_STATE,
            eval_metric=["auc", "aucpr"],
            tree_method="hist",
            **params,
        )
        model.fit(train_X, train_y, eval_set=[(val_model_X, val_model_y)], verbose=False)
        val_raw = model.predict_proba(val_model_X)[:, 1]
        val_auc = float(roc_auc_score(val_model_y, val_raw))
        val_auc_pr = float(average_precision_score(val_model_y, val_raw))
        if val_auc_pr > best_auc_pr or (val_auc_pr == best_auc_pr and val_auc > best_auc):
            best_model = model
            best_name = candidate_name
            best_params = params
            best_auc = val_auc
            best_auc_pr = val_auc_pr

    assert best_model is not None
    val_policy_raw = best_model.predict_proba(val_policy_X)[:, 1]
    calibrator, calibrator_name, calibrator_metrics = _select_calibrator(val_policy_y, val_policy_raw)
    test_raw = best_model.predict_proba(test_X)[:, 1]
    test_calibrated = calibrator.predict(test_raw)
    return {
        "model": best_model,
        "calibrator": calibrator,
        "metrics": _collect_upi_metrics(test_y, test_calibrated),
        "selected_candidate": best_name,
        "selected_params": best_params,
        "val_model_roc_auc": best_auc,
        "val_model_auc_pr": best_auc_pr,
        "selected_calibrator": calibrator_name,
        "val_policy_calibration_metrics": calibrator_metrics,
    }


def _select_calibrator(y_true: np.ndarray, raw_pd: np.ndarray) -> tuple[Any, str, dict[str, float]]:
    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(raw_pd, y_true)
    logistic = LogisticProbabilityCalibrator().fit(raw_pd, y_true)
    iso_pred = isotonic.predict(raw_pd)
    log_pred = logistic.predict(raw_pd)
    iso_metrics = _calibration_metrics(y_true, iso_pred)
    log_metrics = _calibration_metrics(y_true, log_pred)
    if log_metrics["brier_score"] <= iso_metrics["brier_score"]:
        return logistic, "logistic", log_metrics
    return isotonic, "isotonic", iso_metrics


def _collect_upi_metrics(y_true: np.ndarray, calibrated_pd: np.ndarray) -> dict[str, float]:
    y_pred = (calibrated_pd >= DECLINE_THRESHOLD).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "roc_auc": float(roc_auc_score(y_true, calibrated_pd)),
        "auc_pr": float(average_precision_score(y_true, calibrated_pd)),
        "brier_score": float(brier_score_loss(y_true, calibrated_pd)),
        "default_rate": float(np.mean(y_true)),
    }


def _calibration_metrics(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(y_true, pred)),
        "auc_pr": float(average_precision_score(y_true, pred)),
        "brier_score": float(brier_score_loss(y_true, pred)),
    }


def _fit_rare_category_maps(
    df: pd.DataFrame,
    categorical_cols: list[str],
    *,
    min_count: int = 500,
) -> dict[str, set[str]]:
    maps: dict[str, set[str]] = {}
    for col in categorical_cols:
        series = df[col].fillna("Unknown")
        vc = series.value_counts(dropna=False)
        maps[col] = set(vc[vc >= min_count].index.tolist())
    return maps


def _apply_rare_category_maps(
    df: pd.DataFrame,
    categorical_cols: list[str],
    fill_values: dict[str, str],
    rare_maps: dict[str, set[str]],
) -> pd.DataFrame:
    df = df.copy()
    for col in categorical_cols:
        if col not in df.columns:
            continue
        series = df[col].fillna(fill_values.get(col, "Unknown")).replace({"XNA": "Unknown"})
        df[col] = series.where(series.isin(rare_maps.get(col, set())), other="OTHER")
    return df


def _fit_missing_flag_columns(df: pd.DataFrame, *, threshold: float = 0.05) -> list[str]:
    miss_rate = df.isna().mean()
    return miss_rate[(miss_rate >= threshold) & (miss_rate < 1.0)].index.tolist()


def _create_missing_flag_columns(df: pd.DataFrame, flag_cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in flag_cols:
        if col in df.columns:
            df[f"{col}_IS_MISSING"] = df[col].isna().astype("int8")
    return df


def _fit_numeric_imputers(df: pd.DataFrame, numeric_cols: list[str]) -> dict[str, float]:
    imputers: dict[str, float] = {}
    for col in numeric_cols:
        median = df[col].median(skipna=True)
        imputers[col] = 0.0 if pd.isna(median) else float(median)
    return imputers


def _fill_numeric_columns(df: pd.DataFrame, imputers: dict[str, float]) -> pd.DataFrame:
    df = df.copy()
    for col, value in imputers.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(value)
    return df


def _encode_to_columns(
    df: pd.DataFrame,
    categorical_cols: list[str],
    expected_columns: list[str],
) -> pd.DataFrame:
    encoded = pd.get_dummies(df, columns=categorical_cols, dtype=float, drop_first=False)
    for col in expected_columns:
        if col not in encoded.columns:
            encoded[col] = 0.0
    extra = [c for c in encoded.columns if c not in expected_columns]
    if extra:
        encoded = encoded.drop(columns=extra)
    return encoded[expected_columns]


def _align_columns(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in expected_columns:
        if col not in df.columns:
            df[col] = np.nan
    extra = [c for c in df.columns if c not in expected_columns]
    if extra:
        df = df.drop(columns=extra)
    return df[expected_columns]


def _scale_numeric_columns(df: pd.DataFrame, builder: UpiFeatureBuilder) -> pd.DataFrame:
    if builder.scaler_ is None or not builder.numeric_scale_columns_:
        return df
    df = df.copy()
    df[builder.numeric_scale_columns_] = builder.scaler_.transform(df[builder.numeric_scale_columns_])
    return df


def _safe_div(a: Any, b: Any) -> np.ndarray:
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isfinite(a_arr) & np.isfinite(b_arr) & (b_arr != 0), a_arr / b_arr, np.nan)


def _class_balance(target: pd.Series) -> dict[str, float]:
    value_counts = target.value_counts(normalize=True).to_dict()
    return {
        "non_default_rate": float(value_counts.get(0, 0.0)),
        "default_rate": float(value_counts.get(1, 0.0)),
    }


def _decision_from_pd(probability_of_default: float) -> str:
    if probability_of_default < APPROVE_THRESHOLD:
        return "APPROVE"
    if probability_of_default < DECLINE_THRESHOLD:
        return "REVIEW"
    return "DECLINE"


def _write_json(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _load_optional_json(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the standalone UPI credit risk model.")
    parser.add_argument("--dataset-path", default=UPI_DATASET_PATH, help="Path to the UPI CSV dataset.")
    parser.add_argument("--artifact-dir", default=ARTIFACT_DIR, help="Directory for UPI model artifacts.")
    parser.add_argument("--sample-rows", type=int, default=None, help="Optional row limit for smoke training.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    training_report = train_upi_model(
        dataset_path=args.dataset_path,
        artifact_dir=args.artifact_dir,
        sample_rows=args.sample_rows,
    )
    metrics = training_report["metrics"]
    print(f"UPI model version: {training_report['model_version']}")
    print(
        "UPI: "
        f"roc_auc={metrics['roc_auc']:.4f}, "
        f"auc_pr={metrics['auc_pr']:.4f}, "
        f"brier={metrics['brier_score']:.4f}, "
        f"default_rate={metrics['default_rate']:.4f}"
    )
    print(f"Report written to: {training_report['artifacts']['report']}")
