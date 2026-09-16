"""Trainable, interpretable score calibrator for labeled resume/JD pairs."""

import json
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("trained_match_model.json")
DEFAULT_WEIGHTS = {"skill_match": 0.70, "semantic_similarity": 0.30, "evidence_score": 0.0, "bias": 0.0}


def _features(skill_match: float, semantic_similarity: float, evidence_score: float) -> list[float]:
    return [skill_match / 100, semantic_similarity / 100, evidence_score / 100, 1.0]


def load_model() -> dict[str, object]:
    if MODEL_PATH.exists():
        return json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    return {"version": "heuristic-v1", "weights": DEFAULT_WEIGHTS, "trained_examples": 0}


def predict_score(skill_match: float, semantic_similarity: float, evidence_score: float) -> tuple[float, dict[str, object]]:
    model = load_model()
    weights = model["weights"]
    values = _features(skill_match, semantic_similarity, evidence_score)
    coefficients = [weights["skill_match"], weights["semantic_similarity"], weights["evidence_score"], weights["bias"]]
    return round(max(0, min(100, 100 * sum(value * coefficient for value, coefficient in zip(values, coefficients)))), 2), model


def train_model(examples: list[dict[str, float]]) -> dict[str, object]:
    """Fit a bounded linear regressor from independently labeled examples."""
    if len(examples) < 8:
        raise ValueError("At least 8 independently labeled examples are required to train a model.")
    weights = [0.70, 0.30, 0.0, 0.0]
    learning_rate = 0.08
    for _ in range(1500):
        gradient = [0.0] * 4
        for item in examples:
            values = _features(item["skill_match"], item["semantic_similarity"], item.get("evidence_score", 0))
            error = sum(value * weight for value, weight in zip(values, weights)) - item["label"] / 100
            for index, value in enumerate(values):
                gradient[index] += error * value / len(examples)
        weights = [weight - learning_rate * value for weight, value in zip(weights, gradient)]
    model = {"version": "linear-calibrated-v1", "weights": dict(zip(("skill_match", "semantic_similarity", "evidence_score", "bias"), weights)), "trained_examples": len(examples)}
    MODEL_PATH.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model
