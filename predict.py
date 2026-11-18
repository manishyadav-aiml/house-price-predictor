"""Command-line predictor.

Examples
--------
python predict.py                       # predicts for a sample house
python predict.py --MedInc 5.2 --HouseAge 20 --Latitude 37.8 --Longitude -122.3
python predict.py --model improved      # use the improved (feature-engineered) model
"""
import argparse
from pathlib import Path

import joblib
import pandas as pd

from housing_utils import FEATURES, PRICE_UNIT

MODELS = {"baseline": "linear_regression_model.pkl", "improved": "improved_model.pkl"}
DEFAULTS = dict(MedInc=3.5, HouseAge=29, AveRooms=5.2, AveBedrms=1.05,
                Population=1166, AveOccup=2.8, Latitude=34.26, Longitude=-118.49)


def load(which="baseline"):
    path = Path(__file__).parent / "models" / MODELS[which]
    if not path.exists():
        raise SystemExit(f"{path} not found - run the notebook first to train and save the model.")
    return joblib.load(path)


def predict_price(bundle, **values):
    row = pd.DataFrame([{f: float(values[f]) for f in FEATURES}])
    return float(bundle["model"].predict(row)[0]) * PRICE_UNIT


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Predict California median house value")
    ap.add_argument("--model", choices=MODELS, default="baseline")
    for f in FEATURES:
        ap.add_argument(f"--{f}", type=float, default=DEFAULTS[f])
    args = vars(ap.parse_args())
    bundle = load(args.pop("model"))
    price = predict_price(bundle, **args)
    print("Input :", {k: v for k, v in args.items()})
    print(f"Predicted median house value: ${price:,.0f}")
