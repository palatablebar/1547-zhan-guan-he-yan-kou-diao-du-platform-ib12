from math import exp, log
import numpy as np


def mean_link(linear):
    return exp(max(-18., min(18., linear)))


def fit_kernel(rows):
    reserved = np.asarray([item.outcome for item in rows], dtype=float)
    predictors = np.asarray([(1., *item.values) for item in rows], dtype=float)
    beta = np.zeros(predictors.shape[1])
    beta[0] = log(max(.2, float(reserved.mean())))
    penalty = np.identity(predictors.shape[1]) * 2.2
    penalty[0, 0] = 0
    def loss(candidate):
        raw = predictors @ candidate
        bounded = np.clip(raw, -18., 18.)
        return np.sum(np.exp(bounded) - reserved * bounded) + .5 * candidate @ penalty @ candidate
    steps = 0
    for steps in range(1, 28):
        rate = np.exp(np.clip(predictors @ beta, -18., 18.))
        gradient = predictors.T @ (rate - reserved) + penalty @ beta
        hessian = (predictors.T * rate) @ predictors + penalty
        movement = np.linalg.solve(hessian, gradient)
        previous = loss(beta)
        size = 1.
        while size >= 2 ** -12:
            alternative = beta - size * movement
            if loss(alternative) <= previous:
                beta = alternative
                break
            size /= 2.
        if np.linalg.norm(size * movement) < 1e-8:
            break
    return tuple(map(float, beta)), (('样本平均人数', float(reserved.mean())), ('优化迭代', steps))


def score_kernel(parameters, sample):
    terms = tuple(coef * value for coef, value in zip(parameters[1:], sample.values, strict=True))
    return mean_link(parameters[0] + sum(terms)), terms
