# Pitcher P4 vs Non-P4 D1 Model

Model: Logistic Regression with KNN imputer (k=10) and StandardScaler before imputation.

Why this model:
- Simple and interpretable.
- Stable performance vs more complex models on this dataset.
- Cutoff tuned via CV for balanced precision/recall.

Selected cutoff:
- 0.555 (chosen from CV precision/recall trade-off table).

Cross-validated metrics at cutoff 0.555:
- Accuracy: 0.695
- Precision (P4): 0.569
- Recall (P4): 0.550

Notes:
- Trained only on D1 players (Power 4, Mid Major, Low Major).
- Target: Power 4 vs Non-P4 D1.
