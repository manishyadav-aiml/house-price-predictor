"""House Price Predictor - Flask web app (UI + JSON API).
Security items are tagged S1..S20 and explained in docs/SECURITY_CHECKLIST.md."""
import csv, hmac, io, json, math, os, re, secrets, sqlite3, sys, time
from collections import defaultdict, deque
from functools import wraps

import joblib, pandas as pd, sklearn
from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

try:                                          # S1/S2: secrets live in the environment / git-ignored .env
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

import train
from housing_utils import FEATURES, PRICE_UNIT

ENV = os.environ.get("APP_ENV", "production")
SECRET = os.environ.get("SECRET_KEY", "")
if len(SECRET) < 32:                          # S3: no fallback secret, refuse to start
    raise RuntimeError("SECRET_KEY missing or shorter than 32 chars. Run:  python setup_env.py   (creates .env for you)")
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(HERE, "app.db"))
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}   # S19
LIM = {k: int(os.environ.get(k + "_LIMIT", d)) for k, d in {"AUTH": 5, "PREDICT": 60, "BATCH": 10, "FEEDBACK": 5}.items()}   # S17
HISTORY_MAX, BATCH_MAX_ROWS = 50, 500

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config.update(SECRET_KEY=SECRET, DEBUG=False, PROPAGATE_EXCEPTIONS=False,                       # S11/S12
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=(ENV == "production"), PERMANENT_SESSION_LIFETIME=7200,
                  MAX_CONTENT_LENGTH=1024 * 1024)                                                  # S15: 1 MB cap

# ---------------- model ----------------
train.ensure_models()
MODELS = {n: joblib.load(p) for n, p in [("baseline", train.BASELINE_PKL), ("improved", train.IMPROVED_PKL)] if p.exists()}
DEMO = any(b.get("demo", False) for b in MODELS.values())
for _n, _b in MODELS.items():                 # pickles can break across scikit-learn versions
    if _b.get("sklearn_version") not in (None, sklearn.__version__):
        print(f"WARNING: model '{_n}' was trained with scikit-learn {_b['sklearn_version']} but {sklearn.__version__} is installed. If predictions fail, run: python train.py")

# label, min, max, default, step   (single source of truth for UI and server-side validation, S13)
INFO = {"MedInc": ("Median income (x $10,000)", 0.1, 20, 3.5, 0.1), "HouseAge": ("House age (years)", 0, 60, 29, 1),
        "AveRooms": ("Avg rooms per household", 0.5, 50, 5.2, 0.1), "AveBedrms": ("Avg bedrooms per household", 0.1, 20, 1.05, 0.05),
        "Population": ("Block population", 1, 50000, 1166, 1), "AveOccup": ("Avg occupants per household", 0.3, 50, 2.8, 0.1),
        "Latitude": ("Latitude", 32, 42.5, 34.26, 0.01), "Longitude": ("Longitude", -125, -114, -118.49, 0.01)}

# ---------------- database (S8, S16) ----------------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH); g.db.row_factory = sqlite3.Row; g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def _close(_):
    c = g.pop("db", None)
    if c: c.close()

with sqlite3.connect(DB_PATH) as _c:
    _c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user');
    CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        inputs TEXT NOT NULL, price REAL NOT NULL, model TEXT NOT NULL, created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, name TEXT, email TEXT, message TEXT, utm TEXT, created INTEGER);""")
DUMMY_HASH = generate_password_hash("timing-equaliser")

# ---------------- helpers ----------------
TAGS, CTRL = re.compile(r"<[^>]*>?"), re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,}$")

def clean(v, maxlen):                         # S13/S14: type + length check, strip markup and control characters
    if not isinstance(v, str): return None
    v = CTRL.sub("", TAGS.sub("", v)).strip()
    return v if 0 < len(v) <= maxlen else None

def err(msg, code, **extra): return jsonify(error=msg, **extra), code

HITS = defaultdict(deque)
def rate_limit(name):                         # S17 (in-memory: use Redis/flask-limiter with several workers)
    def deco(fn):
        @wraps(fn)
        def inner(*a, **k):
            q, now, limit = HITS[(request.remote_addr, name)], time.monotonic(), LIM[name]
            while q and now - q[0] > 60: q.popleft()
            if len(q) >= limit: return err("Too many requests, please slow down", 429)
            q.append(now); return fn(*a, **k)
        return inner
    return deco

def csrf_token():
    if "csrf" not in session: session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

def current_user():
    uid = session.get("uid")                  # S6: identity only from the signed session, never from request data
    return db().execute("SELECT id,email,role FROM users WHERE id=?", (uid,)).fetchone() if uid else None

def login_required(fn):                       # S4/S5
    @wraps(fn)
    def inner(*a, **k):
        g.user = current_user()
        return fn(*a, **k) if g.user else err("Authentication required", 401)
    return inner

def admin_required(fn):                       # S10
    @wraps(fn)
    @login_required
    def inner(*a, **k):
        return fn(*a, **k) if g.user["role"] == "admin" else err("Forbidden", 403)
    return inner

@app.before_request
def protect_writes():                         # S19: CSRF token + origin check for every state-changing request
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        o = request.headers.get("Origin")
        if o and o != request.host_url.rstrip("/") and o not in ALLOWED_ORIGINS: return err("Forbidden origin", 403)
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session.get("csrf", "\0")):
            return err("Invalid or missing CSRF token", 403)

@app.after_request
def headers(r):                               # S19: security headers + restricted CORS
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                   "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
    if request.path.startswith("/api/"): r.headers["Cache-Control"] = "no-store"
    if ENV == "production": r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    o = request.headers.get("Origin")
    if o and o in ALLOWED_ORIGINS:
        r.headers.update({"Access-Control-Allow-Origin": o, "Access-Control-Allow-Credentials": "true", "Vary": "Origin",
                          "Access-Control-Allow-Headers": "Content-Type, X-CSRF-Token", "Access-Control-Allow-Methods": "GET,POST,DELETE"})
    return r

@app.errorhandler(Exception)
def errors(e):                                # S12: generic messages; details only in server logs
    if isinstance(e, HTTPException):
        return err({413: "File too large (max 1 MB)", 404: "Not found", 405: "Method not allowed"}.get(e.code, "Request failed"), e.code)
    app.logger.exception("unhandled error")
    return err("Internal server error", 500)

# ---------------- prediction ----------------
def parse_house(d):
    """Validate one house. Returns (values, errors). S13: every field checked server-side."""
    vals, errs = {}, {}
    for f in FEATURES:
        label, lo, hi, _, _ = INFO[f]; v = d.get(f) if isinstance(d, dict) else None
        if isinstance(v, bool): v = None
        try: x = float(v)
        except (TypeError, ValueError): x = math.nan
        if not math.isfinite(x): errs[f] = "Enter a number"
        elif not lo <= x <= hi: errs[f] = f"Must be between {lo} and {hi}"
        else: vals[f] = x
    return vals, errs

def predict_prices(rows, which):
    b = MODELS.get(which) or MODELS["baseline"]
    preds = b["model"].predict(pd.DataFrame(rows, columns=FEATURES))
    return [max(float(p), 0.0) * PRICE_UNIT for p in preds], b

@app.get("/")
def index(): return send_from_directory(app.static_folder, "index.html")

@app.get("/<path:filename>")
def public_assets(filename):
    return send_from_directory("public", filename)

@app.get("/health")
def health(): return jsonify(status="ok", models=sorted(MODELS), demo=DEMO)

@app.get("/api/session")
def session_info():
    u = current_user()
    return jsonify(user=dict(u) if u else None, csrf=csrf_token())

@app.get("/api/meta")
def meta():
    ms = {n: {**b["metrics"], "note": b.get("note", "")} for n, b in MODELS.items()}
    b = MODELS["baseline"]
    return jsonify(features=[{"name": f, "label": INFO[f][0], "min": INFO[f][1], "max": INFO[f][2], "default": INFO[f][3], "step": INFO[f][4]} for f in FEATURES],
                   models=ms, demo=DEMO, source=b.get("source", "california-housing"), trained_at=b.get("trained_at", ""))

@app.post("/api/predict")
@rate_limit("PREDICT")
def predict():
    d = request.get_json(silent=True)
    vals, errs = parse_house(d)
    if errs: return err("Please correct the highlighted fields", 400, errors=errs)
    which = d.get("model") if d.get("model") in MODELS else "baseline"
    (price,), b = predict_prices([vals], which)
    u = current_user()
    if u:                                     # S7: history is stored under the session user's id only
        db().execute("INSERT INTO predictions(user_id,inputs,price,model,created) VALUES(?,?,?,?,?)", (u["id"], json.dumps(vals), price, which, int(time.time())))
        db().execute("DELETE FROM predictions WHERE user_id=? AND id NOT IN (SELECT id FROM predictions WHERE user_id=? ORDER BY id DESC LIMIT ?)", (u["id"], u["id"], HISTORY_MAX))
        db().commit()
    return jsonify(price=round(price), error_margin=round(b["metrics"]["mae"] * PRICE_UNIT), model=which, demo=DEMO, saved=bool(u))

@app.post("/api/predict-batch")
@rate_limit("BATCH")
def predict_batch():
    f = request.files.get("file")             # S15: type check, size cap (MAX_CONTENT_LENGTH), row cap, never written to disk
    if not f or not (f.filename or "").lower().endswith(".csv"): return err("Upload a .csv file", 400)
    try: text = f.read().decode("utf-8-sig")
    except UnicodeDecodeError: return err("File must be UTF-8 text", 400)
    rd = csv.DictReader(io.StringIO(text))
    if not rd.fieldnames or not set(FEATURES) <= set(rd.fieldnames): return err("CSV must have columns: " + ", ".join(FEATURES), 400)
    rows = []
    for i, row in enumerate(rd, start=1):
        if i > BATCH_MAX_ROWS: return err(f"Maximum {BATCH_MAX_ROWS} rows per file", 400)
        rows.append(row)
    if not rows: return err("The file has no data rows", 400)
    parsed = [parse_house(r) for r in rows]
    ok = [(i, v) for i, (v, e) in enumerate(parsed) if not e]
    prices = predict_prices([v for _, v in ok], "baseline")[0] if ok else []
    out = [{"row": i + 1, "error": "invalid: " + ", ".join(e)} for i, (_, e) in enumerate(parsed) if e]
    out += [{"row": i + 1, "price": round(p)} for (i, _), p in zip(ok, prices)]
    return jsonify(count=len(rows), results=sorted(out, key=lambda r: r["row"]))

# ---------------- accounts (S4, S17) ----------------
def start_session(uid=None):
    session.clear()                           # fresh session = no fixation; new CSRF token issued
    if uid: session["uid"] = uid; session.permanent = True
    return csrf_token()

@app.post("/api/register")
@rate_limit("AUTH")
def register():
    d = request.get_json(silent=True) or {}
    email, pw = clean(d.get("email"), 254), d.get("password")
    if not email or not EMAIL.match(email) or not isinstance(pw, str) or not 10 <= len(pw) <= 128:
        return err("Enter a valid email and a password of 10-128 characters", 400)
    try:                                      # role is never read from input (S4/S6)
        cur = db().execute("INSERT INTO users(email,pw) VALUES(?,?)", (email.lower(), generate_password_hash(pw))); db().commit()
    except sqlite3.IntegrityError:
        return err("Could not create account", 400)
    return jsonify(user={"id": cur.lastrowid, "email": email.lower(), "role": "user"}, csrf=start_session(cur.lastrowid)), 201

@app.post("/api/login")
@rate_limit("AUTH")
def login():
    d = request.get_json(silent=True) or {}
    email = (clean(d.get("email"), 254) or "").lower(); pw = d.get("password") if isinstance(d.get("password"), str) else ""
    row = db().execute("SELECT id,email,role,pw FROM users WHERE email=?", (email,)).fetchone()
    ok = check_password_hash(row["pw"] if row else DUMMY_HASH, pw)       # same work for unknown users (timing)
    if not (row and ok): return err("Invalid email or password", 401)
    return jsonify(user={"id": row["id"], "email": row["email"], "role": row["role"]}, csrf=start_session(row["id"]))

@app.post("/api/logout")
def logout(): return jsonify(ok=True, csrf=start_session())

# ---------------- per-user history (S5-S7) ----------------
@app.get("/api/history")
@login_required
def history():
    rows = db().execute("SELECT id,inputs,price,model,created FROM predictions WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return jsonify([{"id": r["id"], "inputs": json.loads(r["inputs"]), "price": round(r["price"]), "model": r["model"], "created": r["created"]} for r in rows])

@app.delete("/api/history")
@login_required
def clear_history():
    db().execute("DELETE FROM predictions WHERE user_id=?", (g.user["id"],)); db().commit(); return jsonify(ok=True)

# ---------------- feedback + admin ----------------
@app.post("/api/feedback")
@rate_limit("FEEDBACK")
def feedback():
    d = request.get_json(silent=True) or {}
    name, email, msg = clean(d.get("name"), 80), clean(d.get("email"), 254), clean(d.get("message"), 1000)
    errs = {}
    if not name: errs["name"] = "Please enter your name"
    if not email or not EMAIL.match(email): errs["email"] = "Enter a valid email address"
    if not msg or len(msg) < 10: errs["message"] = "Message must be 10-1000 characters"
    if errs: return err("Please correct the highlighted fields", 400, errors=errs)
    utm = {k: clean(v, 100) for k, v in (d.get("utm") or {}).items() if k.startswith("utm_") and k in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}} if isinstance(d.get("utm"), dict) else {}
    db().execute("INSERT INTO feedback(name,email,message,utm,created) VALUES(?,?,?,?,?)", (name, email, msg, json.dumps(utm), int(time.time()))); db().commit()
    return jsonify(ok=True), 201

@app.get("/api/admin/stats")
@admin_required
def admin_stats():
    q = lambda t: db().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]       # table names are constants, never user input
    return jsonify(users=q("users"), predictions=q("predictions"), feedback=q("feedback"), demo_model=DEMO)

def make_admin(email):                        # admins are created only from the server command line
    with sqlite3.connect(DB_PATH) as c: c.execute("UPDATE users SET role='admin' WHERE email=?", (email.lower(),))

if __name__ == "__main__":
    if sys.argv[1:2] == ["make-admin"] and len(sys.argv) == 3: make_admin(sys.argv[2]); print("done")
    else: app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))   # production: gunicorn app:app
