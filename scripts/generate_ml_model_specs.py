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
from src.models.upi import (
    UPI_BUILDER_FILENAME,
    UPI_CALIBRATOR_FILENAME,
    UPI_DATASET_PATH,
    UPI_MODEL_FILENAME,
    UPI_MODEL_VERSION,
    UPI_REPORT_FILENAME,
    build_upi,
    _load_upi_bundle,
)


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
    annotated = [
        [f"TN\n{cm[0, 0]:,}", f"FP\n{cm[0, 1]:,}"],
        [f"FN\n{cm[1, 0]:,}", f"TP\n{cm[1, 1]:,}"],
    ]
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    sns.heatmap(
        cm,
        annot=annotated,
        fmt="",
        cmap="Blues",
        cbar=False,
        xticklabels=["Predicted negative", "Predicted positive"],
        yticklabels=["Actual negative", "Actual positive"],
        ax=ax,
    )
    ax.set_title(f"{label} confusion matrix: TN / FP / FN / TP")
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
        .dropna()
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
        "evaluation_rows": int(len(y_true)),
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


def _combine_labeled_splits(bundle: Any) -> pd.DataFrame:
    return pd.concat(
        [bundle.train, bundle.val_model, bundle.val_policy, bundle.test],
        axis=0,
        ignore_index=True,
    )


def _combine_upi_splits(bundle: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(
        [bundle["train"], bundle["val_model"], bundle["val_policy"], bundle["test"]],
        axis=0,
        ignore_index=True,
    )


def _write_metrics_csv(rows: list[dict[str, Any]], path: Path) -> None:
    columns = [
        "model",
        "model_family",
        "model_version",
        "feature_count",
        "threshold",
        "evaluation_rows",
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
- Confusion-matrix rows: `{row["evaluation_rows"]}`
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

Legend: TN=true negative, FP=false positive, FN=false negative, TP=true positive.

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
    evaluation_df = _combine_labeled_splits(bundle)
    y_eval = evaluation_df["TARGET"].astype(int).reset_index(drop=True)

    full_builder = joblib.load(artifact_dir / "full_feature_builder.joblib")
    reduced_builder = joblib.load(artifact_dir / "reduced_feature_builder.joblib")
    full_raw_dir = None if getattr(bundle, "uses_flattened_full_input", False) else str(PROJECT_ROOT / "data" / "raw")
    full_X = build_full(
        evaluation_df,
        full_builder,
        raw_dir=full_raw_dir,
        feature_view=DEFAULT_FULL_FEATURE_VIEW,
    ).reset_index(drop=True)
    reduced_X = build_reduced(evaluation_df, reduced_builder).reset_index(drop=True)

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

    upi_dataset = PROJECT_ROOT / UPI_DATASET_PATH
    if upi_dataset.exists():
        upi_artifact_paths = [
            artifact_dir / UPI_BUILDER_FILENAME,
            artifact_dir / UPI_MODEL_FILENAME,
            artifact_dir / UPI_CALIBRATOR_FILENAME,
            artifact_dir / UPI_REPORT_FILENAME,
        ]
        if all(path.exists() for path in upi_artifact_paths):
            stale_status = OUT_DIR / "upi_model_status.md"
            if stale_status.exists():
                stale_status.unlink()
            upi_report = _load_json(artifact_dir / UPI_REPORT_FILENAME)
            upi_bundle = _load_upi_bundle(str(upi_dataset))
            upi_eval_df = _combine_upi_splits(upi_bundle)
            upi_builder = joblib.load(artifact_dir / UPI_BUILDER_FILENAME)
            models.append(
                {
                    "label": "UPI",
                    "prefix": "upi",
                    "X": build_upi(upi_eval_df, upi_builder).reset_index(drop=True),
                    "y": upi_eval_df["TARGET"].astype(int).reset_index(drop=True),
                    "model": joblib.load(artifact_dir / UPI_MODEL_FILENAME),
                    "calibrator": joblib.load(artifact_dir / UPI_CALIBRATOR_FILENAME),
                    "tier": {
                        "model_family": upi_report.get("model_family", "xgboost"),
                        "model_version": upi_report.get("model_version", UPI_MODEL_VERSION),
                        "feature_count": upi_report.get("feature_count", len(upi_builder.encoded_columns_)),
                        "selection": {
                            "candidate": upi_report.get("selected_candidate", "n/a"),
                            "calibrator": upi_report.get("selection", {}).get("calibrator", "n/a"),
                        },
                    },
                }
            )
        else:
            _write_text(
                OUT_DIR / "upi_model_status.md",
                "# UPI Model Status\n\n"
                f"The UPI dataset exists at `{UPI_DATASET_PATH}`, but UPI artifacts are missing. "
                "Run `python -m src.models.upi` and then rerun this generator.\n",
            )

    metric_rows: list[dict[str, Any]] = []
    for item in models:
        pd_scores = _predict_calibrated(item["model"], item["calibrator"], item["X"])
        y_pred = (pd_scores >= DECLINE_THRESHOLD).astype(int)
        model_y = item.get("y", y_eval)
        row = _metric_row(
            item["label"],
            item["tier"].get("model_family", "unknown"),
            item["tier"].get("model_version", "unknown"),
            item["tier"].get("feature_count", item["X"].shape[1]),
            model_y,
            pd_scores,
        )
        metric_rows.append(row)
        _plot_confusion(
            item["label"],
            model_y,
            y_pred,
            PLOTS_DIR / f"{item['prefix']}_confusion_matrix.png",
        )
        _plot_correlation(
            item["label"],
            item["X"],
            model_y,
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
            "confusion_matrix_population": "all labeled splits: train + val_model + val_policy + test",
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
    metric_table = "\n".join(
        [
            "| Model | AUC-ROC | Accuracy | Brier Score | Rows | Feature Count |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            *[
                f"| {row['model']} | {_format_metric(row['auc_roc'])} | {_format_metric(row['accuracy'])} | {_format_metric(row['brier_score'])} | {row['evaluation_rows']} | {row['feature_count']} |"
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
- `upi_model_spec.md`
- `tables/metrics_summary.csv`
- `tables/metrics_summary.json`
- `plots/full_confusion_matrix.png`
- `plots/full_correlation_matrix.png`
- `plots/reduced_confusion_matrix.png`
- `plots/reduced_correlation_matrix.png`
- `plots/upi_confusion_matrix.png`
- `plots/upi_correlation_matrix.png`

## Evaluation Notes
- AUC-ROC is reported as `auc_roc` in machine-readable files.
- Accuracy and confusion matrices use the default-decline threshold `{DECLINE_THRESHOLD}` from `configs/config.py`.
- Confusion matrices are labeled as TN, FP, FN, and TP.
- Confusion matrices and summary metrics use all labeled split rows available to each model: train + val_model + val_policy + test.
- Correlation matrices are built from the top 24 model-input features by absolute correlation with `TARGET`, plus `TARGET`.
- Missing raw Home Credit inputs in this checkout:
{missing_note}
"""
    _write_text(OUT_DIR / "README.md", readme)
    print(f"Wrote ML model specs to {OUT_DIR}")


if __name__ == "__main__":
    main()
