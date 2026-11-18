"""Shared helpers for the California Housing project.

Kept in a separate module (instead of inside the notebook) so that the saved
model pickles can be loaded from any script, e.g. predict.py or app.py.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURES = ["MedInc", "HouseAge", "AveRooms", "AveBedrms",
            "Population", "AveOccup", "Latitude", "Longitude"]
TARGET = "MedHouseVal"          # median house value, in units of $100,000
PRICE_UNIT = 100_000

# (latitude, longitude) of the large coastal metros; prices drop with distance
CITIES = {
    "LA": (34.05, -118.25),
    "SF": (37.77, -122.42),
    "SD": (32.72, -117.16),
    "SJ": (37.34, -121.89),
}


def add_features(X):
    """Feature engineering used by the 'improved' models.

    Accepts a DataFrame (or a NumPy array in FEATURES order) and returns a
    DataFrame with extra columns:
      * ratios      - BedroomRatio, PeoplePerRoom
      * log-scales  - tame the heavy right-skew of count-like features
      * geography   - distance (in degrees) to LA / SF / SD / SJ + nearest city
    """
    if not isinstance(X, pd.DataFrame):
        X = pd.DataFrame(X, columns=FEATURES)
    X = X.copy()

    X["BedroomRatio"] = X["AveBedrms"] / X["AveRooms"]
    X["PeoplePerRoom"] = X["AveOccup"] / X["AveRooms"]

    for col in ["Population", "AveOccup", "AveRooms", "AveBedrms"]:
        X[f"log_{col}"] = np.log1p(X[col])

    dists = []
    for name, (lat, lon) in CITIES.items():
        d = np.sqrt((X["Latitude"] - lat) ** 2 + (X["Longitude"] - lon) ** 2)
        X[f"dist_{name}"] = d
        dists.append(d)
    X["dist_nearest_city"] = np.minimum.reduce(dists)
    return X


def regression_metrics(y_true, y_pred):
    """MAE, RMSE and R2 as plain floats."""
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }
