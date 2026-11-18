# Contributing

Thanks for your interest! This is a learning project, and small improvements are welcome.

## Set up
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python setup_env.py                                     # creates .env with a random SECRET_KEY
```

## Before you open a pull request
1. Run the tests: `python tests/test_app.py` (all checks must pass, no internet needed).
2. If you add an endpoint, validate its input on the server, protect it with the right decorator, and add a test, including one that tries to misuse it.
3. Do not commit `.env`, databases, model files or secrets.
4. Describe what changed and why in the pull request.

## Style
Keep code simple and commented where the reason is not obvious. Follow `.editorconfig`.

## Reporting bugs
Open an issue with steps to reproduce, what you expected and what happened. For security problems follow [SECURITY.md](SECURITY.md) instead.
