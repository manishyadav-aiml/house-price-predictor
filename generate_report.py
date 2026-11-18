"""Builds the short PDF report (Task1_Linear_Regression_Report.pdf).

It reads results.json and the figures/ folder that the notebook produces, so every
number in the report comes from the notebook run - nothing is hard-coded.
Run directly (python generate_report.py) or via the last notebook cell.
"""
import json
from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

NAVY = colors.HexColor("#1f3a5f")
LIGHT = colors.HexColor("#eef2f7")
USD = 100_000


def usd(v):
    return f"${v * USD:,.0f}"


def img(path, width):
    w, h = PILImage.open(path).size
    return Image(str(path), width=width, height=width * h / w)


def build_report(root=None, out_name="Task1_Linear_Regression_Report.pdf"):
    root = Path(root or Path(__file__).parent)
    R = json.loads((root / "results.json").read_text())
    fig = root / "figures"
    ds, bl, split = R["dataset"], R["baseline"], R["split"]

    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.2, leading=12.4, spaceAfter=4)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2)
    h1 = ParagraphStyle("h1", parent=ss["Heading2"], textColor=NAVY, fontSize=12.5,
                        spaceBefore=8, spaceAfter=4)
    title = ParagraphStyle("title", parent=ss["Title"], textColor=NAVY, fontSize=18, leading=22,
                           spaceAfter=2)
    sub = ParagraphStyle("sub", parent=body, alignment=1, textColor=colors.grey)
    cap = ParagraphStyle("cap", parent=body, fontSize=7.8, leading=9.5, textColor=colors.grey,
                         alignment=1, spaceAfter=4)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.4, leading=10.5, spaceAfter=0)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)

    def P(t, s=body):
        return Paragraph(t, s)

    def B(t):
        return Paragraph(t, bullet, bulletText="-")

    def table(rows, widths, header=True):
        data = [[Paragraph(str(c), cellb if (header and i == 0) else cell) for c in r]
                for i, r in enumerate(rows)]
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5cedb")),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if header:
            st += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
            st += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
        t.setStyle(TableStyle(st))
        return t

    S = []
    S += [P("House Price Prediction with Linear Regression", title),
          P("California Housing dataset &nbsp;|&nbsp; AI &amp; ML - Task 1 &nbsp;|&nbsp; "
            f"Manish Kumar Yadav &nbsp;|&nbsp; {date.today():%d %b %Y}", sub), Spacer(1, 6)]

    # 1 ---------------------------------------------------------------- dataset
    S += [P("1. Objective and dataset", h1),
          P("The goal is to walk through a complete machine-learning workflow - data loading, "
            "exploration, preprocessing, training, evaluation and reporting - by predicting the "
            "median house value of a California census block group with a Linear Regression "
            "model. The data is the California Housing dataset shipped with scikit-learn "
            "(1990 US census). Prices are expressed in units of $100,000."),
          table([["Rows", "Features", "Target", "Missing values", "Duplicate rows", "Target range"],
                 [f"{ds['rows']:,}", str(len(ds['features'])), ds["target"], str(ds["missing"]),
                  str(ds["duplicates"]), f"{usd(ds['target_min'])} - {usd(ds['target_max'])}"]],
                [2.1 * cm, 2.0 * cm, 2.9 * cm, 2.9 * cm, 2.8 * cm, 4.3 * cm])]

    # 2 --------------------------------------------------------------------- EDA
    top = R["eda"]["top_corr"][:3]
    top_txt = ", ".join(f"<b>{f}</b> (r = {r:+.2f})" for f, r in top)
    skew = R["eda"]["skewed"]
    S += [P("2. Exploratory data analysis", h1),
          B(f"<b>Target:</b> mean {usd(ds['target_mean'])}, median {usd(ds['target_median'])}. "
            f"{ds['capped_pct']:.1f}% of districts sit exactly at the {usd(ds['target_max'])} "
            "ceiling - a censoring artefact of the survey that no model can see beyond."),
          B(f"<b>Strongest linear relationships with price:</b> {top_txt}."),
          B("<b>Skew and outliers:</b> " + (", ".join(skew) if skew else "none") +
            " are heavily right-skewed with extreme outliers (e.g. districts with hundreds of "
            "rooms per household), which hurts a linear model."),
          B("<b>Geography:</b> expensive districts cluster along the coast around Los Angeles and "
            "the San Francisco Bay Area, so location carries a lot of signal that is non-linear "
            "in latitude/longitude."),
          Spacer(1, 3),
          Table([[img(fig / "target_distribution.png", 8.3 * cm), img(fig / "correlation_heatmap.png", 8.3 * cm)]],
                colWidths=[8.6 * cm, 8.6 * cm]),
          P("Figure 1. Target distribution (left) and feature correlation matrix (right).", cap),
          img(fig / "geographic_prices.png", 8.0 * cm),
          P("Figure 2. Median house value by location.", cap)]

    # 3 -------------------------------------------------------------------- model
    te, tr = bl["test"], bl["train"]
    S += [P("3. Model and evaluation", h1),
          P(f"The data was split {int((1 - split['test_size']) * 100)}/{int(split['test_size'] * 100)} "
            f"into {split['train']:,} training and {split['test']:,} test rows "
            f"(random_state = {split['random_state']}). A scikit-learn <i>Pipeline</i> chains "
            "<b>StandardScaler</b> and <b>LinearRegression</b>; fitting the scaler on training data "
            "only avoids data leakage, and scaling makes the coefficients directly comparable. "
            "Metrics: MAE (average absolute error), RMSE (penalises large errors) and "
            "R<super>2</super> (share of variance explained)."),
          table([["Set", "MAE", "RMSE", "R<super>2</super>"],
                 ["Train", f"{tr['mae']:.3f} ({usd(tr['mae'])})", f"{tr['rmse']:.3f}", f"{tr['r2']:.3f}"],
                 ["Test", f"{te['mae']:.3f} ({usd(te['mae'])})", f"{te['rmse']:.3f}", f"{te['r2']:.3f}"],
                 ["5-fold CV (train)", "-", "-", f"{bl['cv_r2_mean']:.3f} +/- {bl['cv_r2_std']:.3f}"]],
                [4.2 * cm, 4.6 * cm, 3.2 * cm, 4.2 * cm]),
          Spacer(1, 4),
          P(f"On unseen data the baseline is off by about <b>{usd(te['mae'])}</b> on average and explains "
            f"<b>{te['r2'] * 100:.0f}%</b> of the variance in house prices. Train and test scores are close "
            "(and cross-validation agrees), so the model is <b>under-fitting rather than over-fitting</b>: "
            "a straight-line model is simply too simple for this data."),
          img(fig / "diagnostics.png", 17.0 * cm),
          P("Figure 3. Actual vs predicted, residuals vs predicted, and residual distribution (test set).", cap)]

    # 4 ------------------------------------------------------------ improvements
    comp = R["comparison"]
    rows = [["Model", "CV RMSE", "Test MAE", "Test RMSE", "Test R<super>2</super>"]]
    for c in comp:
        rows.append([c["name"], f"{c['cv_rmse']:.3f}", f"{c['mae']:.3f}", f"{c['rmse']:.3f}", f"{c['r2']:.3f}"])
    base = comp[0]
    bestl = next(c for c in comp if c["name"] == R["best_linear"])
    gain = (base["rmse"] - bestl["rmse"]) / base["rmse"] * 100
    nonlin = [c for c in comp if c["kind"] == "non-linear"]
    S += [P("4. Improvement experiments", h1),
          P("Using only the training data (5-fold CV) and then the untouched test set, the baseline was "
            "compared with feature engineering (ratios, log transforms, distance to major cities), "
            "regularisation (RidgeCV) and a non-linear reference model."),
          table(rows, [7.2 * cm, 2.4 * cm, 2.4 * cm, 2.6 * cm, 2.6 * cm]),
          Spacer(1, 4),
          P(f"The best linear model is <b>{bestl['name']}</b>, changing test RMSE by "
            f"<b>{gain:+.1f}%</b> relative to the baseline "
            f"(R<super>2</super> {base['r2']:.3f} to {bestl['r2']:.3f})." +
            (f" The non-linear reference ({nonlin[0]['name']}) reaches R<super>2</super> = "
             f"{nonlin[0]['r2']:.3f}, showing how much non-linear structure a plain linear model leaves "
             "on the table." if nonlin else "")),
          img(fig / "model_comparison.png", 15.0 * cm),
          P("Figure 4. Test RMSE (lower is better) and R<super>2</super> (higher is better) by model.", cap)]

    # 5 -------------------------------------------------------------- conclusion
    S += [KeepTogether([
        P("5. Conclusion, limitations and next steps", h1),
        P(f"A simple, interpretable Linear Regression pipeline gives a solid baseline "
          f"(test R<super>2</super> = {te['r2']:.2f}); <b>median income</b> is by far the most influential "
          "feature. Better results come from richer features and non-linear models rather than from "
          "tuning the linear model itself."),
        P("<b>Limitations:</b> 1990 census data; prices capped at the ceiling; block-group averages "
          "rather than individual houses; not suitable for real valuation decisions."),
        P("<b>Improvement ideas:</b>"),
        B("Handle the capped target (drop or model separately) and use a log-transformed target."),
        B("Polynomial / interaction terms and splines for latitude and longitude."),
        B("Tree-based ensembles (Random Forest, Gradient Boosting) and hyper-parameter search."),
        B("Spatial features such as k-nearest-neighbour average price and distance to the coast."),
        B("Residual analysis by region and price band to find where the model fails most.")])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.8 * cm, 1.0 * cm, "Task 1 - Linear Regression on California Housing")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.0 * cm, f"Page {doc.page}")
        canvas.restoreState()

    out = root / out_name
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.6 * cm,
                            title="House Price Prediction - Linear Regression",
                            author="Manish Kumar Yadav")
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    return out


if __name__ == "__main__":
    print("Report written to", build_report())
