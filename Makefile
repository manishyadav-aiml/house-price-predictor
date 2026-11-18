.PHONY: setup train run test clean
setup:      ## install dependencies and create .env
	pip install -r requirements.txt
	python setup_env.py || true
train:      ## train both models on the real dataset (needs internet once)
	python train.py
run:        ## start the web app on http://127.0.0.1:5000
	python app.py
test:       ## run all automated checks (no internet needed)
	python tests/test_app.py
clean:
	rm -rf __pycache__ tests/__pycache__ models/*.pkl models/metrics.json app.db
