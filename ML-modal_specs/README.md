# ML Model Specifications

Generated from `artifacts/reproducibility_report.json` and the persisted model artifacts.

Metrics were generated from the real processed/raw training artifacts.

## Summary Metrics
| Model | AUC-ROC | Accuracy | Brier Score | Rows | Feature Count |
| --- | ---: | ---: | ---: | ---: | ---: |
| FULL | 0.8338 | 0.9205 | 0.0634 | 307511 | 269 |
| REDUCED | 0.7776 | 0.9178 | 0.0670 | 307511 | 147 |
| UPI | 0.8504 | 0.9227 | 0.0623 | 99988 | 17 |

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
- Accuracy and confusion matrices use the default-decline threshold `0.35` from `configs/config.py`.
- Confusion matrices are labeled as TN, FP, FN, and TP.
- Confusion matrices and summary metrics use all labeled split rows available to each model: train + val_model + val_policy + test.
- Correlation matrices are built from the top 24 model-input features by absolute correlation with `TARGET`, plus `TARGET`.
- Missing raw Home Credit inputs in this checkout:
- None
