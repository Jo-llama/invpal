"""Combine (logistic regression) + calibrate (isotonic) the per-field signals into a single
confidence score."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from .dataset import Row
from .features import rows_to_matrix


@dataclass
class ConfidenceModel:
    logistic: LogisticRegression
    isotonic: IsotonicRegression

    def predict(self, rows: list[Row]) -> np.ndarray:
        x, _ = rows_to_matrix(rows)
        raw = self.logistic.predict_proba(x)[:, 1]
        return self.isotonic.predict(raw)


def fit(train_rows: list[Row], calib_rows: list[Row]) -> ConfidenceModel:
    x_train, y_train = rows_to_matrix(train_rows)
    logistic = LogisticRegression(max_iter=1000)
    logistic.fit(x_train, y_train)

    x_calib, y_calib = rows_to_matrix(calib_rows)
    raw_calib = logistic.predict_proba(x_calib)[:, 1]
    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(raw_calib, y_calib)

    return ConfidenceModel(logistic=logistic, isotonic=isotonic)
