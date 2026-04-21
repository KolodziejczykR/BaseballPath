# PCI V2 Rework Plan — Calibrated Model Integration

This document captures everything needed to rework the Player Competitiveness Index (PCI) for the new calibrated outfielder models (version_04202026). The old PCI was designed around overconfident ensemble models; the new calibrated XGBoost models produce fundamentally different probability distributions, and the PCI must be updated to match.

---

## 1. Old vs New Model Architecture

### Old Models (version_08072025)
- **D1 model:** Hierarchical ensemble of XGBoost + LightGBM + DNN + SVM, 47 engineered features (percentiles, elite flags, interactions, region)
- **P4 model:** Similar ensemble architecture
- **Probability behavior:** Overconfident — probabilities clustered near 0 and 1, with strong players regularly hitting 0.85+. Mean D1 probability for actual D1 players was ~0.70+
- **Threshold:** D1 at 0.62, P4 at 0.38/0.40 (elite/non-elite split)

### New Models (version_04202026)
- **D1 model:** Single XGBoost (n_estimators=500, max_depth=4, lr=0.01) with isotonic calibration (CalibratedClassifierCV). 7 production-realistic features: `height`, `weight`, `exit_velo_max`, `distance_max`, `sixty_time`, `of_velo`, `bat_speed_max`
- **P4 model:** Single XGBoost (n_estimators=300, max_depth=3, lr=0.03, reg_alpha=1.5, reg_lambda=5.0, min_child_weight=8) with isotonic calibration. 8 features: the same 7 + `d1_prob` as a meta-feature
- **Probability behavior:** Well-calibrated — a probability of 0.40 means ~40% of players at that score are actually D1. Probabilities are spread more evenly, with D1 players averaging ~0.37 in out-of-fold and strong D1 players typically in the 0.45-0.65 range. Very few players exceed 0.75
- **Threshold:** D1 at 0.45, P4 at 0.50 (standard)
- **Eval metrics:** D1 AUC=0.77, Brier=0.158; P4 AUC=0.71, Brier=0.158

### Key Implication
Every constant in `competitiveness.py` that references a probability value was tuned for the old overconfident distributions. They all need recalibration.

---

## 2. Routing Logic Change — Send More Players to P4 Model

### Current Routing (outfielder_pipeline.py)
```
D1 prediction (threshold 0.62) → if D1 predicted → P4 prediction
                                → if Non-D1 → stop, return Non-D1
```

### New Routing
```
D1 prediction (threshold 0.45) → if d1_prob >= 0.45 (D1 predicted) → P4 prediction
                                → if 0.33 < d1_prob < 0.45 (borderline) → STILL route to P4 model
                                → if d1_prob <= 0.33 → stop, return Non-D1
```

### Why the 0.33 Soft Floor
With calibrated probabilities, a player at d1_prob=0.40 is genuinely competitive for D1 programs — they just didn't clear the 0.45 classification threshold. These borderline players may still have P4-level tools (e.g., elite exit velo) that the P4 model can detect. Cutting them off at 0.45 loses information.

The 0.33 floor means: "If there's at least a 1-in-3 chance this player is D1-caliber, let the P4 model weigh in." Players below 0.33 are confidently Non-D1 and don't benefit from P4 evaluation.

### Implementation Notes
- `outfielder_pipeline.py` line 59: change the `if not d1_result.d1_prediction` early return to check `d1_result.d1_probability > 0.33` instead
- The P4 model already accepts `d1_probability` as a meta-feature, so borderline players will naturally get lower P4 probabilities (the model learned the d1_prob signal)
- For players routed to P4 despite d1_prediction=False, their `effective_tier()` will still treat them as Non-P4 D1 at most (the demotion logic prevents inflation)

---

## 3. Relative Weighting — P4 Probability Should Have Less Impact Than D1

### Why
- **D1 model is stronger:** AUC 0.77 vs 0.71, trained on 8,516 samples vs ~1,800 D1-only samples
- **P4 dataset is small:** Only 490 P4-committed players in training. The model has a 0.167 overfit gap (train AUC - test AUC), meaning its probabilities carry more noise
- **P4 is a refinement, not a classification:** The D1 model already does the heavy lifting of separating college-caliber from non-college. P4 vs Non-P4 D1 is a finer distinction within an already-selected population

### Current PCI Adjustments (competitiveness.py:404-426)
```python
# These are ALL wrong for calibrated models
if tier == POWER_4_D1:    base += (p4_prob - 0.65) * 8.0
elif tier == NON_P4_D1:   base += (d1_prob - 0.65) * 6.0
elif tier == NON_D1:      base += (d1_prob - 0.15) * 25.0
```

**Problems:**
1. Centers are at 0.65 — calibrated D1 players average ~0.50-0.55 in production (higher than OOF 0.37 since production trains on full data). The 0.65 center means most players get negative adjustments
2. P4 multiplier (8.0) is higher than D1 multiplier (6.0) — this is backwards given model confidence
3. Non-D1 multiplier (25.0) with center at 0.15 creates huge swings for small probability differences

### Proposed Adjustment Philosophy
```
D1 tier adjustment:   highest multiplier, most trusted signal
P4 tier adjustment:   lower multiplier than D1, noisier signal
Non-D1 adjustment:    moderate multiplier, d1_prob tells us "how close to D1"
```

### Suggested New Centers and Multipliers (to be tuned)
These are starting points — the exact values need empirical tuning against known player outcomes:

```python
# P4 tier: p4_prob center ~0.50, lower multiplier
if tier == POWER_4_D1:    base += (p4_prob - 0.50) * 5.0

# Non-P4 D1 tier: d1_prob center ~0.55, moderate multiplier
elif tier == NON_P4_D1:   base += (d1_prob - 0.55) * 8.0

# Non-D1 tier: d1_prob center ~0.25, moderate multiplier
elif tier == NON_D1:      base += (d1_prob - 0.25) * 15.0
```

**Key changes:**
- P4 multiplier (5.0) is now LESS than D1 multiplier (8.0), reflecting model confidence hierarchy
- Centers shifted down to match calibrated probability distributions
- Non-D1 multiplier reduced from 25.0 to 15.0 to prevent extreme swings

---

## 4. effective_tier() Floor Rework

### Current Floors (competitiveness.py:167-189)
```python
p4_floor = 0.55   # Demote P4 → Non-P4 D1 if p4_prob < 0.55
d1_floor = 0.50   # Demote Non-P4 D1 → Non-D1 if d1_prob < 0.50
```

### Problem
With calibrated models, a d1_prob of 0.50 is actually quite strong — it means the player has a genuine 50/50 shot at D1. The old floor of 0.50 would demote players who are solidly in the D1 conversation.

Similarly, p4_prob of 0.55 with a calibrated model is a strong P4 signal. The 0.55 floor is too aggressive.

### Proposed New Floors
```python
p4_floor = 0.40   # Only demote P4 if p4_prob is clearly below chance
d1_floor = 0.38   # Only demote D1 if d1_prob is well below threshold
```

**Rationale:**
- d1_floor at 0.38 means: "If the D1 model gives you less than 38% calibrated probability, you shouldn't be treated as D1 regardless of what the threshold-based classification said." This catches edge cases where a player barely clears 0.45 on some metric combination but the overall picture is weak
- p4_floor at 0.40 means: "If the P4 model gives you less than 40%, don't treat this as a P4 player." Given the P4 model's noisier predictions, we want a floor that catches clear misclassifications without being overly aggressive
- These floors work WITH the routing change (section 2) — a player routed to P4 with d1_prob=0.35 who gets p4_prob=0.30 will be demoted all the way back to Non-D1 by effective_tier()

---

## 5. PCI Band Rework

### Current Bands (competitiveness.py:49-53)
```python
TIER_PCI_BANDS = {
    POWER_4_D1: (69.0, 100.0),   # 31-point range
    NON_P4_D1: (35.0, 88.0),     # 53-point range
    NON_D1: (0.0, 45.0),         # 45-point range
}
```

### Issues
- Bands overlap: Non-P4 D1 goes up to 88 and P4 starts at 69, meaning a strong Non-P4 D1 player (PCI 85) looks more competitive than a weak P4 player (PCI 72). This is intentional for school matching but the overlap width needs to match calibrated probability ranges
- Non-D1 goes up to 45 and Non-P4 D1 starts at 35 — same overlap intent

### Recommended Approach
Keep the overlapping band structure (it's correct for matching — a strong D2 player should match with some low-D1 schools). But the bands may need width adjustment once we see the actual PCI distribution from calibrated models. Specifically:
- Run a batch of known players through the new pipeline
- Check that the PCI distribution has reasonable separation between tiers
- Adjust band edges if tiers are collapsing into each other or spreading too far apart

### Band Adjustment Considerations
- If calibrated probabilities compress the adjustment term (because the multiplier * deviation from center is smaller), the within-band spread will shrink. This might require widening bands or increasing multipliers
- The P4 band bottom (69.0) should remain high enough that P4 players always match with D1 schools
- The Non-D1 band top (45.0) should remain low enough that Non-D1 players don't get matched with competitive D1 programs

---

## 6. How d1_prob Works as a Meta-Feature in the P4 Model

The P4 model receives `d1_prob` as its 8th feature (alongside the 7 core physical/performance metrics). This was generated using out-of-fold cross-validation predictions to avoid data leakage during training.

### Production Flow
1. D1 model runs on player features → produces `d1_probability`
2. `d1_probability` is passed directly to the P4 model as the `d1_prob` feature
3. P4 model uses `d1_prob` alongside physical metrics to predict P4 probability

### Why This Matters for PCI
- `d1_prob` is the #2 most important feature in the P4 model. It encodes "overall D1-ness" as a continuous signal
- This means d1_prob already influences p4_prob — so the PCI should NOT double-count by giving both probabilities full weight in the adjustment formula
- If you apply a strong d1_prob adjustment AND a strong p4_prob adjustment, you're effectively counting d1_prob twice (once directly, once through its influence on p4_prob)
- This is another reason P4's PCI multiplier should be lower than D1's

---

## 7. Implementation Checklist

### Pipeline Changes (outfielder_pipeline.py)
- [ ] Update model version paths from `version_08072025` to `version_04202026`
- [ ] Update routing logic: route to P4 if `d1_prob > 0.33` (not just if `d1_prediction == True`)
- [ ] Update the `prediction_pipeline` imports for new model versions
- [ ] Ensure `d1_probability` is passed correctly as meta-feature to P4 model

### PCI Changes (competitiveness.py)
- [ ] Update `effective_tier()` floors: `d1_floor=0.38`, `p4_floor=0.40`
- [ ] Update `ml_based_pci()` probability centers: P4 from 0.65→0.50, Non-P4 D1 from 0.65→0.55, Non-D1 from 0.15→0.25
- [ ] Update `ml_based_pci()` multipliers: P4 from 8.0→5.0, Non-P4 D1 from 6.0→8.0, Non-D1 from 25.0→15.0
- [ ] Review `TIER_PCI_BANDS` after running batch predictions with new models
- [ ] Validate PCI distribution across a sample of known players

### Prediction Pipeline (models_of/version_04202026/)
- [ ] Write `prediction_pipeline.py` for new D1 model (load calibrated_xgb_model.pkl, apply 7 features, threshold 0.45)
- [ ] Write `prediction_pipeline.py` for new P4 model (load calibrated_xgb_model.pkl, apply 8 features including d1_prob, threshold 0.50)
- [ ] Ensure model_config.json and feature_metadata.json are referenced correctly

### Testing
- [ ] Unit test effective_tier() with calibrated probability ranges
- [ ] Unit test ml_based_pci() with calibrated probability ranges
- [ ] Integration test full pipeline: player features → D1 prediction → P4 prediction → PCI
- [ ] Batch validation: run ~50 known players, verify PCI distribution makes sense
- [ ] Edge cases: d1_prob at 0.33 boundary, p4_prob at floor boundary, borderline tier transitions

---

## 8. Constants Quick Reference

| Parameter | Old Value | New Value | Reason |
|---|---|---|---|
| D1 threshold | 0.62 | 0.45 | Calibrated probs are lower |
| P4 threshold | 0.38/0.40 | 0.50 | Standard threshold for calibrated model |
| P4 routing floor | N/A (binary gate) | 0.33 | Allow borderline D1 players into P4 model |
| effective_tier d1_floor | 0.50 | 0.38 | Calibrated 0.38 = meaningful D1 signal |
| effective_tier p4_floor | 0.55 | 0.40 | Calibrated 0.40 = meaningful P4 signal |
| P4 PCI center | 0.65 | 0.50 | Match calibrated P4 distribution |
| P4 PCI multiplier | 8.0 | 5.0 | P4 model is noisier, less confident |
| Non-P4 D1 PCI center | 0.65 | 0.55 | Match calibrated D1 distribution |
| Non-P4 D1 PCI multiplier | 6.0 | 8.0 | D1 model is strongest signal |
| Non-D1 PCI center | 0.15 | 0.25 | Match calibrated Non-D1 distribution |
| Non-D1 PCI multiplier | 25.0 | 15.0 | Reduce extreme swings |

---

## 9. Risk Notes

- **P4 model overfit gap (0.167):** The P4 model trained on ~1,800 D1 players with only 490 P4-committed. Its probabilities are noisier than the D1 model's. The PCI must account for this by weighting P4 less heavily. As more data becomes available, retrain and re-evaluate
- **Calibrated probabilities are NOT confidence scores:** A calibrated probability of 0.45 doesn't mean "we're 45% sure this player is D1." It means "of all players the model scores at 0.45, about 45% actually committed to D1." This is a frequency statement, not a certainty statement. The PCI adjustments should treat probabilities as population-level signals, not individual guarantees
- **Double-counting d1_prob:** Since d1_prob feeds into the P4 model, PCI adjustments for P4-tier players should primarily reference p4_prob (which already incorporates d1_prob), not stack both. The current proposed formulas handle this by only using p4_prob for P4-tier and d1_prob for Non-P4 D1 tier
- **Band tuning is empirical:** The suggested multipliers and centers are starting points derived from model evaluation statistics. They need validation against a batch of known players before going to production
