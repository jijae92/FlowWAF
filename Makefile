.PHONY: deps test build deploy delete demo seed
deps:
	pip install -r requirements.txt
test:
	pytest -q --cov=backend --cov-report=term-missing
build:
	sam build
deploy:
	sam deploy --guided --stack-name flow-waf-anomaly
delete:
	sam delete --stack-name flow-waf-anomaly
demo:
	python scripts/seed_synthetic_logs.py --mode waf --minutes 60
seed:
	python scripts/seed_synthetic_logs.py --mode vpc --minutes 60