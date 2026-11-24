# Score Scale

## Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2

The cross-encoder outputs raw logits (unbounded floats, typically -12 to +12).

### Conversion

Temperature-scaled sigmoid with T=4:

```
score = 1 / (1 + e^(-raw_logit / 4))
```

The temperature T=4 spreads the sigmoid across the model's full output range, so that even deeply negative logits produce distinguishable non-zero values.

### Why T=4?

Plain sigmoid (T=1) maps the range -12 to -10 into 0.000006 to 0.000045 — indistinguishable at any reasonable display precision. With T=4, the same range maps to 0.047 to 0.068 — clearly different, visible at 2-3 decimal places.

| Raw logit | Sigmoid (T=1) | Sigmoid (T=4) |
|---|---|---|
| -12 | 0.000006 | 0.047 |
| -11 | 0.000017 | 0.060 |
| -10 | 0.000045 | 0.076 |
| -5 | 0.007 | 0.223 |
| -2 | 0.119 | 0.378 |
| 0 | 0.500 | 0.500 |
| 2 | 0.881 | 0.622 |
| 5 | 0.993 | 0.777 |
| 10 | 1.000 | 0.924 |

### Labels

| Score range | Label | Raw logit range | Meaning |
|---|---|---|---|
| >= 0.70 | High | >= 3.4 | Strong match |
| 0.30 - 0.69 | Medium | -3.4 to 3.3 | Decent match |
| < 0.30 | Low | < -3.4 | Weak match |

### Threshold

The score_threshold setting operates on the 0-1 scaled score. A threshold of 0.10 maps to raw logit > -8.8. A threshold of 0.30 maps to raw logit > -3.4.

### What this score is used for

1. **Threshold filter**: `reranker.py` — chunks below threshold are dropped
2. **Label badge**: `ResultsSection.jsx scoreLevel()` — High/Medium/Low
3. **Displayed value**: Source card shows the 0-1 score with adaptive precision

Dense similarity, BM25, and RRF are used only to select candidates for the reranker. They are shown in the Score Breakdown as diagnostics but are not used for decisions or labels.

The raw logit is preserved as `rerank_score_raw` and shown in the badge tooltip.
