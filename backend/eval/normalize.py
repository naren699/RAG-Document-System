import re
import string

ARTICLES = {"a", "an", "the"}

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_answer(text: str) -> str:
    """Lowercase, strip punctuation, remove articles (a/an/the), collapse whitespace."""
    text = text.lower()
    text = text.translate(_PUNCT_TABLE)
    tokens = text.split()
    tokens = [t for t in tokens if t not in ARTICLES]
    return " ".join(tokens)


def exact_match(prediction: str, gold: str) -> int:
    """1 if normalized prediction equals normalized gold, else 0."""
    return int(normalize_answer(prediction) == normalize_answer(gold))


def token_f1(prediction: str, gold: str) -> float:
    """Token-level F1 between normalized prediction and gold."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = set(pred_tokens) & set(gold_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)
