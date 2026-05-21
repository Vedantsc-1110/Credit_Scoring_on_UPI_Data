"""Generate model metric specs and plots for the persisted ML tiers.

The script reads the current training artifacts, rebuilds the evaluation split
used by the training workflow, and writes a compact report bundle to
``ML-modal_specs``.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)

from configs.config import ARTIFACT_DIR, DATA_DIR, DECLINE_THRESHOLD
from src.feature_engineering import build_full, build_reduced
from src.models.train import (
    DEFAULT_FULL_FEATURE_VIEW,
    RAW_TABLE_NAMES,
    _generate_synthetic_bundle,
    _has_real_training_inputs,
    _load_real_bundle,
)
from src.models.upi import UPI_DATASET_PATH


OUT_DIR = PROJECT_ROOT / "ML-modal_specs"
PLOTS_DIR = OUT_DIR / "plots"
TABLES_DIR = OUT_DIR / "tables"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _predict_calibrated(model: Any, calibrator: Any, X: pd.DataFrame) -> pd.Series:
    raw_pd = model.predict_proba(X)[:, 1]
    calibrated = calibrator.predict(raw_pd)
    return pd.Series(calibrated, index=X.index, name="calibrated_pd")


def _plot_confusion(label: str, y_true: pd.Series, y_pred: pd.Series, path: Path) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        cbar=False,
        xticklabels=["Predicted non-default", "Predicted default"],
        yticklabels=["Actual non-default", "Actual default"],
        ax=ax,
    )
    ax.set_title(f"{label} confusion matrix")
    ax.set_xlabel("Prediction")
    ax.set_ylabel("Actual")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_correlation(label: str, X: pd.DataFrame, y_true: pd.Series, png_path: Path, csv_path: Path) -> None:
    frame = X.copy()
    frame["TARGET"] = y_true.to_numpy()
    corr_to_target = (
        frame.corr(numeric_only=True)["TARGET"]
        .drop("TARGET", errors="ignore")
        .abs()
        .sort_values(ascending=False)
    )
    top_cols = corr_to_target.head(24).index.tolist() + ["TARGET"]
    corr = frame[top_cols].corr(numeric_only=True)
    corr.to_csv(csv_path)

    fig, ax = plt.subplots(figsize=(13, 10))
    sns.heatmap(
        corr,
        cmap="RdBu_r",
        center=0,
        vmin=-1,
        vmax=1,
        linewidths=0.25,
        linecolor="white",
        square=False,
        ax=ax,
    )
    ax.set_title(f"{label} top feature correlation matrix")
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def _metric_row(
    label: str,
    model_family: str,
    model_version: str,
    feature_count: int,
    y_true: pd.Series,
    pd_scores: pd.Series,
) -> dict[str, Any]:
    y_pred = (pd_scores >= DECLINE_THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "model": label,
        "model_family": model_family,
        "model_version": model_version,
        "feature_count": int(feature_count),
        "threshold": float(DECLINE_THRESHOLD),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "auc_roc": float(roc_auc_score(y_true, pd_scores)),
        "brier_score": float(brier_score_loss(y_true, pd_scores)),
        "default_rate": float(y_true.mean()),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def _load_evaluation_bundle(report: dict[str, Any]) -> Any:
    raw_dir = PROJECT_ROOT / "data" / "raw"
    processed_dir = PROJECT_ROOT / DATA_DIR
    if report.get("mode") == "real" and _has_real_training_inputs(str(processed_dir), str(raw_dir)):
        return _load_real_bundle(str(processed_dir), str(raw_dir))
    return _generate_synthetic_bundle()


def _write_metrics_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "model",
        "model_family",
        "model_version",
        "feature_count",
        "threshold",
        "accuracy",
        "auc_roc",
        "brier_score",
        "default_rate",
        "tn",
        "fp",
        "fn",
        "tp",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _format_metric(value: float) -> str:
    return f"{value:.4f}"


def _write_model_markdown(row: dict[str, Any], plot_prefix: str, report_tier: dict[str, Any]) -> None:
    title = row["model"]
    content = f"""# {title} Model Spec

## Overview
- Model family: `{row["model_family"]}`
- Model version: `{row["model_version"]}`
- Feature count: `{row["feature_count"]}`
- Decision threshold for confusion matrix / accuracy: `{row["threshold"]}`
- Selection candidate: `{report_tier.get("selection", {}).get("candidate", "n/a")}`
- Calibrator: `{report_tier.get("selection", {}).get("calibrator", "n/a")}`

## Metrics
| Metric | Value |
| --- | ---: |
| AUC-ROC | {_format_metric(row["auc_roc"])} |
| Accuracy | {_format_metric(row["accuracy"])} |
| Brier Score | {_format_metric(row["brier_score"])} |
| Default Rate | {_format_metric(row["default_rate"])} |

## Confusion Matrix
![{title} confusion matrix](plots/{plot_prefix}_confusion_matrix.png)

Counts: TN={row["tn"]}, FP={row["fp"]}, FN={row["fn"]}, TP={row["tp"]}.

## Correlation Matrix
![{title} correlation matrix](plots/{plot_prefix}_correlation_matrix.png)

CSV table: [tables/{plot_prefix}_correlation_matrix.csv](tables/{plot_prefix}_correlation_matrix.csv)
"""
    _write_text(OUT_DIR / f"{plot_prefix}_model_spec.md", content)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    PLOTS_DIR.mkdir(exist_ok=True)
    TABLES_DIR.mkdir(exist_ok=True)

    artifact_dir = PROJECT_ROOT / ARTIFACT_DIR
    report_path = artifact_dir / "reproducibility_report.json"
    report = _load_json(report_path)
    bundle = _load_evaluation_bundle(report)
    y_test = bundle.test["TARGET"].astype(int).reset_index(drop=True)

    full_builder = joblib.load(artifact_dir / "full_feature_builder.joblib")
    reduced_builder = joblib.load(artifact_dir / "reduced_feature_builder.joblib")
    full_X = build_full(bundle.test, full_builder, feature_view=DEFAULT_FULL_FEATURE_VIEW).reset_index(drop=True)
    reduced_X = build_reduced(bundle.test, reduced_builder).reset_index(drop=True)

    models = [
        {
            "label": "FULL",
            "prefix": "full",
            "X": full_X,
            "model": joblib.load(artifact_dir / "full_model.joblib"),
            "calibrator": joblib.load(artifact_dir / "full_calibrator.joblib"),
            "tier": report["tiers"]["FULL"],
        },
        {
            "label": "REDUCED",
            "prefix": "reduced",
            "X": reduced_X,
            "model": joblib.load(artifact_dir / "reduced_model.joblib"),
            "calibrator": joblib.load(artifact_dir / "reduced_calibrator.joblib"),
            "tier": report["tiers"]["REDUCED"],
        },
    ]

    metric_rows: list[dict[str, Any]] = []
    for item in models:
        pd_scores = _predict_calibrated(item["model"], item["calibrator"], item["X"])
        y_pred = (pd_scores >= DECLINE_THRESHOLD).astype(int)
        row = _metric_row(
            item["label"],
            item["tier"].get("model_family", "unknown"),
            item["tier"].get("model_version", "unknown"),
            item["tier"].get("feature_count", item["X"].shape[1]),
            y_test,
            pd_scores,
        )
        metric_rows.append(row)
        _plot_confusion(
            item["label"],
            y_test,
            y_pred,
            PLOTS_DIR / f"{item['prefix']}_confusion_matrix.png",
        )
        _plot_correlation(
            item["label"],
            item["X"],
            y_test,
            PLOTS_DIR / f"{item['prefix']}_correlation_matrix.png",
            TABLES_DIR / f"{item['prefix']}_correlation_matrix.csv",
        )
        _write_model_markdown(row, item["prefix"], item["tier"])

    _write_metrics_csv(metric_rows, TABLES_DIR / "metrics_summary.csv")
    _write_json(
        TABLES_DIR / "metrics_summary.json",
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_report": str(report_path.relative_to(PROJECT_ROOT)),
            "evaluation_mode": report.get("mode", "unknown"),
            "decision_threshold": DECLINE_THRESHOLD,
            "metrics": metric_rows,
        },
    )

    raw_dir = PROJECT_ROOT / "data" / "raw"
    missing_raw_inputs = [
        str((raw_dir / name).relative_to(PROJECT_ROOT))
        for name in RAW_TABLE_NAMES
        if not (raw_dir / name).exists()
    ]
    upi_dataset = PROJECT_ROOT / UPI_DATASET_PATH
    upi_note = f"""# UPI Model Status

The standalone UPI model is defined in `src/models/upi.py`, but its required raw dataset is not present in this checkout:

- Expected dataset: `{UPI_DATASET_PATH}`
- Present: `{upi_dataset.exists()}`

Because there is no UPI artifact and no labeled UPI evaluation dataset, AUC-ROC, accuracy, Brier score, confusion matrix, and correlation matrix were not generated for UPI in this report bundle.
"""
    _write_text(OUT_DIR / "upi_model_status.md", upi_note)

    metric_table = "\n".join(
        [
            "| Model | AUC-ROC | Accuracy | Brier Score | Feature Count |",
            "| --- | ---: | ---: | ---: | ---: |",
            *[
                f"| {row['model']} | {_format_metric(row['auc_roc'])} | {_format_metric(row['accuracy'])} | {_format_metric(row['brier_score'])} | {row['feature_count']} |"
                for row in metric_rows
            ],
        ]
    )
    source_note = (
        "The real processed/raw training files were not present, so the project training workflow used its deterministic synthetic fallback."
        if report.get("mode") == "synthetic"
        else "Metrics were generated from the real processed/raw training artifacts."
    )
    missing_note = "\n".join(f"- `{path}`" for path in missing_raw_inputs) or "- None"
    readme = f"""# ML Model Specifications

Generated from `artifacts/reproducibility_report.json` and the persisted model artifacts.

{source_note}

## Summary Metrics
{metric_table}

## Included Files
- `full_model_spec.md`
- `reduced_model_spec.md`
- `upi_model_status.md`
- `tables/metrics_summary.csv`
- `tables/metrics_summary.json`
- `plots/full_confusion_matrix.png`
- `plots/full_correlation_matrix.png`
- `plots/reduced_confusion_matrix.png`
- `plots/reduced_correlation_matrix.png`

## Evaluation Notes
- AUC-ROC is reported as `auc_roc` in machine-readable files.
- Accuracy and confusion matrices use the default-decline threshold `{DECLINE_THRESHOLD}` from `configs/config.py`.
- Correlation matrices are built from the top 24 model-input features by absolute correlation with `TARGET`, plus `TARGET`.
- Missing raw Home Credit inputs in this checkout:
{missing_note}
"""
    _write_text(OUT_DIR / "README.md", readme)
    print(f"Wrote ML model specs to {OUT_DIR}")


if __name__ == "__main__":
    main()
