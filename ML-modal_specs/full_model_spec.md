# FULL Model Spec

## Overview
- Model family: `xgboost`
- Model version: `full_v2.1.0`
- Feature count: `114`
- Decision threshold for confusion matrix / accuracy: `0.35`
- Selection candidate: `xgboost_full`
- Calibrator: `isotonic`

## Metrics
| Metric | Value |
| --- | ---: |
| AUC-ROC | 0.7499 |
| Accuracy | 0.7312 |
| Brier Score | 0.1738 |
| Default Rate | 0.7016 |

## Confusion Matrix
![FULL confusion matrix](plots/full_confusion_matrix.png)

Counts: TN=27, FP=164, FN=8, TP=441.

## Correlation Matrix
![FULL correlation matrix](plots/full_correlation_matrix.png)

CSV table: [tables/full_correlation_matrix.csv](tables/full_correlation_matrix.csv)
