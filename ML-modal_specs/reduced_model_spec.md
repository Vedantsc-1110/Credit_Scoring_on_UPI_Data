# REDUCED Model Spec

## Overview
- Model family: `xgboost`
- Model version: `reduced_v2.1.0`
- Feature count: `147`
- Decision threshold for confusion matrix / accuracy: `0.35`
- Confusion-matrix rows: `307511`
- Selection candidate: `tuned_a`
- Calibrator: `isotonic`

## Metrics
| Metric | Value |
| --- | ---: |
| AUC-ROC | 0.7776 |
| Accuracy | 0.9178 |
| Brier Score | 0.0670 |
| Default Rate | 0.0807 |

## Confusion Matrix
![REDUCED confusion matrix](plots/reduced_confusion_matrix.png)

Counts: TN=280115, FP=2571, FN=22717, TP=2108.

Legend: TN=true negative, FP=false positive, FN=false negative, TP=true positive.

## Correlation Matrix
![REDUCED correlation matrix](plots/reduced_correlation_matrix.png)

CSV table: [tables/reduced_correlation_matrix.csv](tables/reduced_correlation_matrix.csv)
