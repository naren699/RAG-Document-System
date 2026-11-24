import math


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score confidence interval for a proportion.

    Returns (lower, upper) as floats in [0, 1].
    """
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z ** 2 / total
    center = (p + z ** 2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * total)) / total) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))
