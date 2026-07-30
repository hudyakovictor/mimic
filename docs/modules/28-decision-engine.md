# Module 28: Decision engine

**Путь:** `services/worker/app/decision/`

## Файлы

### `aggregator.py`
```python
"""
MG-STUB: агрегация scores по всем фразам → final decision.
"""
from dataclasses import dataclass

@dataclass
class Decision:
    job_id: str
    label: str                # CONSISTENT|SUSPICIOUS|INSUFFICIENT_DATA
    risk_score: float         # 0..1
    quality_score: float      # 0..1
    model_version: str
    model_checksum: str
    evidence: list[dict]
    phrase_instances: list[dict]

# Label thresholds
RISK_THRESHOLDS = {
    "CONSISTENT": 0.35,
    "SUSPICIOUS": 0.65,
}

def aggregate(phrase_scores: list[dict], quality: "QualityAssessment",
              has_mature_baseline: bool) -> Decision:
    """phrase_scores: [{word, similarity, evidence}, ...]
    similarity ∈ [0, 1], 1 = identical, 0 = very different.
    """
    if not phrase_scores:
        return Decision(label="INSUFFICIENT_DATA", risk_score=0.0,
                       quality_score=quality.score, ...)

    similarities = [p["similarity"] for p in phrase_scores]
    # aggregate by weighted mean (by evidence contribution)
    weighted_sum = sum(p["similarity"] * (1 + sum(abs(e["contribution"]) for e in p["evidence"]))
                       for p in phrase_scores)
    weights = sum(1 + sum(abs(e["contribution"]) for e in p["evidence"])
                  for p in phrase_scores)
    mean_similarity = weighted_sum / max(weights, 1)
    risk_score = 1.0 - mean_similarity

    if not has_mature_baseline:
        # add INSUFFICIENT_BASELINE evidence
        for p in phrase_scores:
            p["evidence"].append({
                "code": "INSUFFICIENT_BASELINE",
                "contribution": 0.0,
                "message": "Less than 10 verified samples for this word",
            })

    if risk_score < RISK_THRESHOLDS["CONSISTENT"]:
        label = "CONSISTENT"
    elif risk_score >= RISK_THRESHOLDS["SUSPICIOUS"]:
        label = "SUSPICIOUS"
    else:
        label = "INSUFFICIENT_DATA"

    # collect top evidence
    all_evidence = []
    for p in phrase_scores:
        for e in p["evidence"]:
            all_evidence.append({
                **e,
                "word": p["word"],
                "start_ms": p["start_ms"],
                "end_ms": p["end_ms"],
            })
    all_evidence.sort(key=lambda x: -abs(x["contribution"]))
    top_evidence = all_evidence[:10]

    return Decision(
        job_id="...",
        label=label,
        risk_score=risk_score,
        quality_score=quality.score,
        model_version="statistical-v1",
        model_checksum="",
        evidence=top_evidence,
        phrase_instances=phrase_scores,
    )
```

### `persistence.py`
```python
"""
MG-STUB: запись Decision в БД (append-only).
"""
async def persist_decision(session, decision: Decision) -> str:
    dec_row = Decision(
        id=uuid4(),
        job_id=decision.job_id,
        label=decision.label,
        risk_score=decision.risk_score,
        quality_score=decision.quality_score,
        model_version=decision.model_version,
        model_checksum=decision.model_checksum,
        evidence=decision.evidence,
        phrase_instances=decision.phrase_instances,
    )
    session.add(dec_row)
    await session.commit()
    return dec_row.id
```
