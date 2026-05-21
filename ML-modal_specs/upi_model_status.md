# UPI Model Status

The standalone UPI model is defined in `src/models/upi.py`, but its required raw dataset is not present in this checkout:

- Expected dataset: `data\raw\final_base_with_upi_corrected.csv`
- Present: `False`

Because there is no UPI artifact and no labeled UPI evaluation dataset, AUC-ROC, accuracy, Brier score, confusion matrix, and correlation matrix were not generated for UPI in this report bundle.
