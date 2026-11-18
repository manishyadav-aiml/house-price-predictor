# Security Policy

## Supported versions
Only the latest release on the `main` branch receives security fixes.

## Reporting a vulnerability
Please **do not open a public issue** for security problems.

1. Go to the repository's **Security** tab and choose **Report a vulnerability** (GitHub private vulnerability reporting).
2. Include what you found, how to reproduce it, and the impact you expect.

You can expect an acknowledgement within 7 days and a fix or an explanation within 30 days. Please give me reasonable time to fix the issue before sharing it publicly.

## Scope
In scope: the Flask app (`app.py`), the web UI (`static/`), authentication, CSV upload handling and the model-loading code.
Out of scope: issues that need a compromised server, denial of service through huge traffic, and the accuracy of the model's predictions.

## How the project is hardened
The 20-point checklist (secrets, authentication, CSRF, validation, rate limiting, security headers and more) and the automated tests that check it are described in [docs/SECURITY_CHECKLIST.md](docs/SECURITY_CHECKLIST.md).

## For people deploying this project
* Set a long random `SECRET_KEY` and never commit `.env`.
* Serve over HTTPS and keep `APP_ENV=production`.
* Only load model files (`*.pkl`) that you trained yourself; pickle files can run code when loaded.
* Run `./check_secrets.sh` before publishing a repository that already has history.
