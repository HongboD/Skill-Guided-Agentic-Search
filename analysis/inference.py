"""Paired-topic bootstrap, sign randomization, and Holm adjustment."""
import numpy as np

def paired_summary(values, *, bootstrap_samples=10000, randomization_samples=100000, seed=20261029):
    delta = np.asarray(values, dtype=float)
    if delta.ndim != 1 or not len(delta) or (not np.isfinite(delta).all()):
        raise ValueError('finite_paired_topic_differences_required')
    rng = np.random.default_rng(seed)
    means = np.empty(bootstrap_samples)
    for start in range(0, bootstrap_samples, 1000):
        count = min(1000, bootstrap_samples - start)
        means[start:start + count] = rng.choice(delta, (count, len(delta))).mean(axis=1)
    observed = abs(delta.mean())
    exceed = 0
    if len(delta) <= 16:
        total = 2 ** len(delta)
        for start in range(0, total, 1000):
            signs = (np.arange(start, min(total, start + 1000))[:, None] >> np.arange(len(delta)) & 1) * 2 - 1
            exceed += int(np.sum(np.abs((signs * delta).mean(axis=1)) >= observed - 1e-12))
        p, method = (exceed / total, 'exact_two_sided_sign_randomization')
    else:
        for start in range(0, randomization_samples, 1000):
            count = min(1000, randomization_samples - start)
            signs = rng.integers(0, 2, (count, len(delta))) * 2 - 1
            exceed += int(np.sum(np.abs((signs * delta).mean(axis=1)) >= observed - 1e-12))
        p, method = ((exceed + 1) / (randomization_samples + 1), 'monte_carlo_two_sided_sign_randomization')
    return {'topics': len(delta), 'mean_difference': float(delta.mean()), 'paired_bootstrap_95_interval': np.quantile(means, [0.025, 0.975]).tolist(), 'p_value': p, 'test': method, 'seed': seed}

def holm(values):
    pairs = sorted(values.items(), key=lambda row: (row[1], row[0]))
    result, previous = ({}, 0.0)
    for i, (name, p) in enumerate(pairs):
        if not 0 <= p <= 1:
            raise ValueError('invalid_p_value')
        previous = min(1.0, max(previous, (len(pairs) - i) * p))
        result[name] = previous
    return result
