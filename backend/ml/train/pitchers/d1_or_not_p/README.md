# Pitcher D1 vs Non-D1 Model

Model: Logistic Regression with KNN imputer (k=10) and StandardScaler before imputation.

Why this model:
- Best performance among tested models for this dataset.
- Simple and interpretable vs complex ensembles.
- Threshold tuned via CV to optimize precision with guardrails.

Selected cutoff:
- 0.571 (CV-selected threshold for precision/recall balance).

Cross-validated metrics at cutoff 0.571:
- Accuracy: 0.768
- Precision (D1): 0.657
- Recall (D1): 0.702

Notes:
- Target: D1 vs Non-D1.
- Features: pitcher physicals + pitch metrics + missingness flags.
