# ML Model Specifications

Generated from `artifacts/reproducibility_report.json` and the persisted model artifacts.

The real processed/raw training files were not present, so the project training workflow used its deterministic synthetic fallback.

## Summary Metrics
| Model | AUC-ROC | Accuracy | Brier Score | Feature Count |
| --- | ---: | ---: | ---: | ---: |
| FULL | 0.7499 | 0.7312 | 0.1738 | 114 |
| REDUCED | 0.6914 | 0.7047 | 0.1884 | 69 |

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
- Accuracy and confusion matrices use the default-decline threshold `0.35` from `configs/config.py`.
- Correlation matrices are built from the top 24 model-input features by absolute correlation with `TARGET`, plus `TARGET`.
- Missing raw Home Credit inputs in this checkout:
- `data\raw\bureau.csv`
- `data\raw\previous_application.csv`
- `data\raw\installments_payments.csv`
- `data\raw\POS_CASH_balance.csv`
- `data\raw\credit_card_balance.csv`
