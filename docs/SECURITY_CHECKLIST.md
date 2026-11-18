# Security checklist: how each item is handled

Verify everything with `python tests/test_app.py` (58 checks) and, optionally, `python tests/e2e_browser.py` (36 browser checks).

| # | Item | How it is handled | Where |
|---|------|-------------------|-------|
| 1 | Secure API keys | The only secret is `SECRET_KEY`, read from the environment | `app.py` |
| 2 | Hide `.env` files | `.env*` is git-ignored; only `.env.example` is committed | `.gitignore` |
| 3 | No hard-coded secrets | App refuses to start without a 32+ character `SECRET_KEY` | `app.py` |
| 4 | Authentication | Register/login/logout, salted password hashes, signed HttpOnly session, new session on login/logout | `app.py` |
| 5 | Permissions server-side | `login_required` and `admin_required` on every protected route | `app.py` |
| 6 | Don't trust frontend user IDs | The user id comes only from the session; `user_id`/`role` in request bodies are ignored | tested |
| 7 | Isolate user data | History queries always filter by the session user; history capped at 50 rows | tested |
| 8 | Lock down the database | Parameterised SQL only, foreign keys on, DB file git-ignored. For a hosted database use a least-privilege account | `app.py` |
| 9 | Firebase / Supabase / storage | Not used (SQLite). If you switch: Supabase needs Row Level Security on every table and never expose the `service_role` key; Firebase needs owner-only rules and App Check | notes only |
| 10 | Protect admin routes | `/api/admin/stats` needs role `admin`; admins can only be created from the server command line (`python app.py make-admin EMAIL`) | tested |
| 11 | Debug off in production | `DEBUG=False`, no debug flag in `app.run`; use gunicorn | tested |
| 12 | Hide detailed errors | Global handler returns generic messages; details only in server logs | tested |
| 13 | Validate inputs server-side | Type, finite-number and range checks for all 8 features, plus email, password and text lengths | tested |
| 14 | Sanitize user content | Tags and control characters are stripped on input; the UI inserts text with `textContent` only | tested |
| 15 | Secure file uploads | The only upload is the batch CSV: `.csv` only, UTF-8 only, 1 MB and 500-row caps, never saved to disk, never executed | tested |
| 16 | Prevent SQL/NoSQL injection | Only `?` placeholders; no string-built SQL with user input | tested |
| 17 | Rate-limit login and signup | 5 attempts/min/IP on login and register; limits on predict, batch and feedback too. In-memory: use Redis or flask-limiter with several workers and configure the proxy so the real client IP is seen | tested |
| 18 | Check Git history for secrets | `./check_secrets.sh`, and for a deeper scan gitleaks or trufflehog. If a secret was ever committed, rotate it first | script only |
| 19 | Security headers, restrict CORS | CSP (no inline scripts or styles), nosniff, frame deny, referrer, permissions, HSTS in production, CSRF token on every write, origin check, CORS only for `ALLOWED_ORIGINS` | tested |
| 20 | Test as an untrusted user | `tests/test_app.py` | 58 checks |

## Known limits
* Rate-limit counters live in memory and reset on restart.
* SQLite suits a demo or small site; use PostgreSQL for heavier traffic.
* Model files are loaded with `joblib` (pickle). Only load model files you trained yourself.
* Always serve over HTTPS in production (the session cookie is `Secure` when `APP_ENV=production`).
