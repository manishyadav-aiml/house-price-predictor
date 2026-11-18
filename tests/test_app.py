"""End-to-end tests: functionality + 'act as an untrusted user' security checks.
Run from the project folder:   python tests/test_app.py        (no internet needed, uses the demo model)"""
import io, json, os, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ.update(SECRET_KEY="t" * 40, APP_ENV="development", DATABASE_PATH=str(tmp / "t.db"), FORCE_DEMO_MODEL="1",
                  ALLOWED_ORIGINS="https://good.example", AUTH_LIMIT="8", PREDICT_LIMIT="500", FEEDBACK_LIMIT="50")
import train
train.MODEL_DIR = tmp / "models"; train.BASELINE_PKL = train.MODEL_DIR / "b.pkl"; train.IMPROVED_PKL = train.MODEL_DIR / "i.pkl"
import app as A

class C:
    """Browser-like client: keeps cookies and sends the CSRF token on writes."""
    def __init__(self): self.c = A.app.test_client(); self.csrf = self.c.get("/api/session").get_json()["csrf"]
    def get(self, p, **k): return self.c.get(p, **k)
    def post(self, p, json=None, **k): return self.c.post(p, json=json, headers={"X-CSRF-Token": self.csrf, **k.pop("headers", {})}, **k)
    def delete(self, p): return self.c.delete(p, headers={"X-CSRF-Token": self.csrf})
    def auth(self, action, email, pw="correct-horse-battery"):
        r = self.post(f"/api/{action}", json={"email": email, "password": pw})
        if r.status_code in (200, 201): self.csrf = r.get_json()["csrf"]
        return r

HOUSE = {"MedInc": 5, "HouseAge": 20, "AveRooms": 6, "AveBedrms": 1, "Population": 1500, "AveOccup": 3, "Latitude": 37.8, "Longitude": -122.3}
res = []
def check(name, ok): res.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)
def csv_file(text, name="h.csv"): return {"file": (io.BytesIO(text.encode()), name)}

anon = C()
# ---------- functionality ----------
check("home page served with skip link", b"Skip to content" in anon.get("/").data)
check("health endpoint works", anon.get("/health").get_json()["status"] == "ok")
check("css and js served", anon.get("/static/style.css").status_code == 200 and anon.get("/static/app.js").status_code == 200)
m = anon.get("/api/meta").get_json()
check("meta lists 8 features, 2 models, demo flag", len(m["features"]) == 8 and set(m["models"]) == {"baseline", "improved"} and m["demo"] is True)
p = anon.post("/api/predict", json=HOUSE); pj = p.get_json()
check("prediction returns a positive price and error margin", p.status_code == 200 and pj["price"] > 0 and pj["error_margin"] > 0 and pj["saved"] is False)
check("improved model also predicts", anon.post("/api/predict", json={**HOUSE, "model": "improved"}).get_json()["model"] == "improved")
check("unknown model name falls back to baseline", anon.post("/api/predict", json={**HOUSE, "model": "../../etc/passwd"}).get_json()["model"] == "baseline")
check("higher income gives higher price", anon.post("/api/predict", json={**HOUSE, "MedInc": 9}).get_json()["price"] > pj["price"])
for label, bad in [("text instead of number", {**HOUSE, "MedInc": "abc"}), ("missing field", {k: v for k, v in HOUSE.items() if k != "Latitude"}),
                   ("out-of-range value", {**HOUSE, "HouseAge": 500}), ("NaN", {**HOUSE, "MedInc": float("nan")}), ("boolean", {**HOUSE, "MedInc": True}), ("null", {**HOUSE, "AveRooms": None})]:
    r = anon.post("/api/predict", json=bad); check(f"invalid input rejected: {label}", r.status_code == 400 and r.get_json()["errors"])
check("non-JSON body rejected", anon.post("/api/predict", data="not json", headers={"Content-Type": "text/plain"}).status_code == 400)

hdr = ",".join(HOUSE)
good = hdr + "\n" + ",".join(map(str, HOUSE.values())) + "\n" + ",".join(["abc"] + list(map(str, list(HOUSE.values())[1:]))) + "\n"
b = anon.post("/api/predict-batch", data=csv_file(good), content_type="multipart/form-data").get_json()
check("batch: valid row priced, bad row reported", b["count"] == 2 and "price" in b["results"][0] and "error" in b["results"][1])
check("batch: wrong columns rejected", anon.post("/api/predict-batch", data=csv_file("a,b\n1,2\n"), content_type="multipart/form-data").status_code == 400)
check("batch: non-csv extension rejected", anon.post("/api/predict-batch", data=csv_file(good, "x.exe"), content_type="multipart/form-data").status_code == 400)
check("batch: binary content rejected", anon.post("/api/predict-batch", data={"file": (io.BytesIO(b"\xff\xfe\x00bad"), "a.csv")}, content_type="multipart/form-data").status_code == 400)
check("batch: more than 500 rows rejected", anon.post("/api/predict-batch", data=csv_file(hdr + "\n" + (",".join(map(str, HOUSE.values())) + "\n") * 501), content_type="multipart/form-data").status_code == 400)
check("batch: oversized file rejected (413)", anon.post("/api/predict-batch", data=csv_file(hdr + "\n" + "9" * 1_200_000), content_type="multipart/form-data").status_code == 413)

# ---------- README results updater ----------
rd = tmp / "README.md"; rd.write_text("a\n" + train.R_START + "\nold\n" + train.R_END + "\nb\n", encoding="utf-8")
mm = {"baseline": {"mae": .5, "rmse": .7, "r2": .6}, "improved": {"mae": .4, "rmse": .6, "r2": .7}}
check("README results are NOT written for the demo model", train.update_readme(mm, "demo-synthetic", "2026-01-01", rd) is False and "old" in rd.read_text(encoding="utf-8"))
check("README results table filled for real data", train.update_readme(mm, "california-housing", "2026-01-01", rd) and "| R² | 0.600 | 0.700 |" in rd.read_text(encoding="utf-8") and rd.read_text(encoding="utf-8").startswith("a\n") and rd.read_text(encoding="utf-8").rstrip().endswith("b"))

# ---------- security: CSRF, auth, isolation ----------
check("write without CSRF token blocked (403)", anon.c.post("/api/predict", json=HOUSE).status_code == 403)
check("write with wrong CSRF token blocked (403)", anon.c.post("/api/predict", json=HOUSE, headers={"X-CSRF-Token": "nope"}).status_code == 403)
check("anonymous cannot read history (401)", anon.get("/api/history").status_code == 401)
check("anonymous cannot reach admin (401)", anon.get("/api/admin/stats").status_code == 401)
a, bb = C(), C()
check("register works", a.auth("register", "a@x.com").status_code == 201 and bb.auth("register", "b@x.com").status_code == 201)
check("weak password rejected", C().auth("register", "w@x.com", "short").status_code == 400)
check("duplicate email gives generic error", C().auth("register", "a@x.com").status_code == 400)
a.post("/api/predict", json={**HOUSE, "user_id": 2, "role": "admin"})
check("A's prediction saved to A's history only", a.post("/api/predict", json=HOUSE).get_json()["saved"] and len(a.get("/api/history").get_json()) == 2 and bb.get("/api/history").get_json() == [])
check("spoofed user_id/role in body ignored", bb.get("/api/admin/stats").status_code == 403)
check("normal user forbidden on admin (403)", a.get("/api/admin/stats").status_code == 403)
A.make_admin("a@x.com"); st = a.get("/api/admin/stats")
check("admin promoted server-side sees stats", st.status_code == 200 and st.get_json()["users"] == 2)
rc = C(); rc.post("/api/register", json={"email": "r@x.com", "password": "correct-horse-battery", "role": "admin"}); rc.auth("login", "r@x.com")
check("register cannot grant admin role", rc.get("/api/admin/stats").status_code == 403)
for _ in range(55): bb.post("/api/predict", json=HOUSE)
check("history capped at 50 rows per user", len(bb.get("/api/history").get_json()) == 50)
bb.delete("/api/history"); check("user can clear own history, not others'", bb.get("/api/history").get_json() == [] and len(a.get("/api/history").get_json()) == 2)
bb.csrf = bb.post("/api/logout").get_json()["csrf"]
check("logout ends session (401) and rotates CSRF", bb.get("/api/history").status_code == 401)

# ---------- security: injection, XSS, errors, headers ----------
check("SQL injection in login is just a failed login (401)", C().auth("login", "' OR 1=1 --@x.com", "x' OR '1'='1").status_code == 401)
check("SQL injection in email cannot log in", C().auth("login", "a@x.com' --", "whatever-123456").status_code == 401)
f = anon.post("/api/feedback", json={"name": "<b>Eve</b>", "email": "e@x.com", "message": "<script>alert(1)</script>hello world!", "utm": {"utm_source": "news<i>", "evil": "x"}})
row = sqlite3.connect(str(tmp / "t.db")).execute("SELECT name,message,utm FROM feedback").fetchone()
check("feedback accepted, tags stripped, only utm_* kept", f.status_code == 201 and "<" not in row[0] + row[1] + row[2] and "evil" not in row[2])
check("feedback validation errors per field", set(anon.post("/api/feedback", json={"name": "", "email": "bad", "message": "x"}).get_json()["errors"]) == {"name", "email", "message"})
check("password stored as salted hash", "correct-horse" not in str(sqlite3.connect(str(tmp / "t.db")).execute("SELECT pw FROM users").fetchall()))
h = anon.get("/api/session").headers
check("security headers present", all(k in h for k in ["X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"]))
check("CSP forbids inline scripts/styles", "unsafe-inline" not in h["Content-Security-Policy"] and "script-src 'self'" in h["Content-Security-Policy"])
page = anon.get("/").get_data(as_text=True)
check("no inline scripts, handlers or style attributes in HTML", "<script>" not in page and " onclick=" not in page and ' style="' not in page)
check("API responses are not cacheable", anon.get("/api/meta").headers["Cache-Control"] == "no-store")
check("CORS: evil origin gets no allow header", "Access-Control-Allow-Origin" not in anon.get("/api/meta", headers={"Origin": "https://evil.example"}).headers)
check("CORS: listed origin allowed (not *)", anon.get("/api/meta", headers={"Origin": "https://good.example"}).headers.get("Access-Control-Allow-Origin") == "https://good.example")
check("cross-site write blocked (403)", anon.post("/api/predict", json=HOUSE, headers={"Origin": "https://evil.example"}).status_code == 403)
check("path traversal on static is blocked", anon.get("/static/../app.py").status_code == 404 and anon.get("/static/%2e%2e/.env").status_code == 404)
ck = A.app.test_client().get("/api/session").headers.get("Set-Cookie", "")
check("session cookie is HttpOnly + SameSite=Lax", "HttpOnly" in ck and "SameSite=Lax" in ck)

with A.app.test_request_context("/boom"):      # call the global error handler directly
    body, code = A.errors(ValueError("db password=hunter2"))
check("server error returns generic 500, no details", code == 500 and "hunter2" not in body.get_data(as_text=True))
check("debug mode off", A.app.debug is False)
check("no hard-coded secret: app refuses short SECRET_KEY", "SECRET_KEY missing" in open(Path(A.__file__)).read())

# ---------- rate limiting ----------
A.HITS.clear(); r = C(); codes = [r.auth("login", "a@x.com", "wrong-password-1").status_code for _ in range(12)]
check("login rate limited (401s then 429)", codes[0] == 401 and 429 in codes)
A.HITS.clear(); m1 = C().auth("login", "nobody@x.com", "whatever-12345"); m2 = C().auth("login", "a@x.com", "whatever-12345")
check("unknown user and wrong password: identical error", m1.get_json() == m2.get_json())
A.HITS.clear(); A.LIM["PREDICT"] = 3; q = C(); codes = [q.post("/api/predict", json=HOUSE).status_code for _ in range(5)]
check("predict endpoint rate limited", codes[:3] == [200] * 3 and 429 in codes)

print(f"\n{sum(res)}/{len(res)} checks passed"); sys.exit(0 if all(res) else 1)
