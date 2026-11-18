"""Train + evaluate the models and save them to models/.   python train.py [--demo]

Uses the real California Housing dataset (downloaded by scikit-learn, or data/california_housing.csv).
If neither is available it falls back to a SYNTHETIC demo dataset and marks the model as demo=True,
so the web app can still start and clearly warns the user.
"""
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path

import joblib, numpy as np, pandas as pd, sklearn
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from housing_utils import FEATURES, TARGET, add_features, regression_metrics

ROOT = Path(__file__).parent
MODEL_DIR, DATA_CSV, SEED = ROOT / "models", ROOT / "data" / "california_housing.csv", 42
BASELINE_PKL, IMPROVED_PKL = MODEL_DIR / "linear_regression_model.pkl", MODEL_DIR / "improved_model.pkl"


def make_demo_data(n=6000):
    """Synthetic stand-in with the same columns. NOT real housing data."""
    r = np.random.default_rng(0)
    lat, lon = r.uniform(32.5, 42, n), r.uniform(-124.3, -114.3, n)
    inc = r.lognormal(1.2, .5, n).clip(.5, 15)
    df = pd.DataFrame({"MedInc": inc, "HouseAge": r.integers(1, 53, n).astype(float),
                       "AveRooms": r.lognormal(1.65, .3, n), "AveBedrms": r.lognormal(.05, .15, n),
                       "Population": r.lognormal(7, .7, n).round(), "AveOccup": r.lognormal(1, .3, n),
                       "Latitude": lat, "Longitude": lon})
    y = .4 * inc + 2.5 * np.exp(-np.hypot(lat - 34, lon + 118.2) / 2) + r.normal(0, .5, n)
    df[TARGET] = np.clip(y, .15, 5.0)
    return df


def load_data(demo=False):
    if demo:
        return make_demo_data(), "demo-synthetic"
    try:
        from sklearn.datasets import fetch_california_housing
        df = fetch_california_housing(as_frame=True).frame.copy()
        DATA_CSV.parent.mkdir(exist_ok=True); df.to_csv(DATA_CSV, index=False)
        return df, "california-housing"
    except Exception as err:
        print("Dataset download failed:", type(err).__name__)
    return make_demo_data(), "demo-synthetic"      # a stale/synthetic local CSV is never trusted as real data


def _pipe(model, engineer=False):
    steps = [("features", FunctionTransformer(add_features))] if engineer else []
    return Pipeline(steps + [("scaler", StandardScaler()), ("model", model)])


def train(demo=False):
    df, source = load_data(demo)
    X_tr, X_te, y_tr, y_te = train_test_split(df[FEATURES], df[TARGET], test_size=0.2, random_state=SEED)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = {}
    for name, pipe, path, note in [
        ("baseline", _pipe(LinearRegression()), BASELINE_PKL, "StandardScaler + LinearRegression"),
        ("improved", _pipe(RidgeCV(alphas=np.logspace(-3, 3, 13)), True), IMPROVED_PKL, "RidgeCV + engineered features")]:
        pipe.fit(X_tr, y_tr)
        m = regression_metrics(y_te, pipe.predict(X_te))
        MODEL_DIR.mkdir(exist_ok=True)
        joblib.dump({"model": pipe, "features": FEATURES, "metrics": m, "note": note, "source": source,
                     "demo": source != "california-housing", "trained_at": stamp,
                     "sklearn_version": sklearn.__version__}, path)
        out[name] = m
        print(f"{name:9s} MAE {m['mae']:.3f}  RMSE {m['rmse']:.3f}  R2 {m['r2']:.3f}   ({source})")
    (MODEL_DIR / "metrics.json").write_text(json.dumps({"source": source, "trained_at": stamp, **out}, indent=2))
    if update_readme(out, source, stamp):
        print("README.md results table updated with the real metrics.")
    return out


README = ROOT / "README.md"
R_START, R_END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def results_table(m, source, stamp):
    usd = lambda v: f"${v * 100_000:,.0f}"
    cell = lambda k, fmt: f"{fmt(m['baseline'][k])} | {fmt(m['improved'][k])}"
    rows = [f"| MAE | {m['baseline']['mae']:.3f} (about {usd(m['baseline']['mae'])}) | {m['improved']['mae']:.3f} (about {usd(m['improved']['mae'])}) |",
            f"| RMSE | {m['baseline']['rmse']:.3f} | {m['improved']['rmse']:.3f} |",
            f"| R² | {m['baseline']['r2']:.3f} | {m['improved']['r2']:.3f} |"]
    return ("| Metric | Linear Regression (baseline) | Improved (Ridge + features) |\n|---|---|---|\n" + "\n".join(rows) +
            f"\n\n_Measured on the 20% hold-out test set (`random_state=42`). Prices are in units of $100,000. Trained {stamp} on the {source} dataset._")


def update_readme(m, source, stamp, readme=README):
    """Writes the real metrics into the README results block. Never writes demo/synthetic numbers."""
    if source != "california-housing" or not readme.exists():
        return False
    text = readme.read_text(encoding="utf-8")
    if R_START not in text or R_END not in text:
        return False
    head, rest = text.split(R_START, 1)
    _, tail = rest.split(R_END, 1)
    readme.write_text(head + R_START + "\n" + results_table(m, source, stamp) + "\n" + R_END + tail, encoding="utf-8")
    return True


def ensure_models():
    """Called by the web app: train on first start if no saved model exists."""
    if not BASELINE_PKL.exists():
        train(demo=os.environ.get("FORCE_DEMO_MODEL") == "1")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--demo", action="store_true", help="use synthetic data")
    train(ap.parse_args().demo)
