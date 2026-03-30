.PHONY: help dev dev-api dev-download test lint build chart-install chart-upgrade chart-template chart-uninstall clean

API_PORT ?= 8000

help:                    ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev:                     ## Run full local environment (download + API)
	docker compose up --build

dev-api:                 ## Run API only (assumes data already downloaded)
	docker compose up --build api
dev-download:            ## Run downloader only
	docker compose run --rm downloader
test:                    ## Run tests
	PYTHONPATH=api python -m pytest tests/ -v
lint:                    ## Run linters
	PYTHONPATH=api python -m ruff check api/ tests/
	PYTHONPATH=api python -m mypy api/
build:                   ## Build Docker images
	docker build -t incognipwn-api:latest ./api
	docker build -t incognipwn-downloader:latest ./downloader
chart-template:          ## Debug: render Helm templates
	helm template incognipwn ./chart/incognipwn -n incognipwn
chart-template-dev:      ## Debug: render Helm templates (dev values)
	helm template incognipwn ./chart/incognipwn -n incognipwn -f ./chart/incognipwn/values/dev.yaml
chart-install:           ## Install chart on cluster
	helm install incognipwn ./chart/incognipwn -n incognipwn --create-namespace
chart-install-dev:       ## Install chart with dev values
	helm install incognipwn ./chart/incognipwn -n incognipwn --create-namespace -f ./chart/incognipwn/values/dev.yaml
chart-install-prod:      ## Install chart with prod values
	helm install incognipwn ./chart/incognipwn -n incognipwn --create-namespace -f ./chart/incognipwn/values/prod.yaml
chart-upgrade:           ## Upgrade chart on cluster
	helm upgrade incognipwn ./chart/incognipwn -n incognipwn
chart-uninstall:         ## Uninstall chart from cluster
	helm uninstall incognipwn -n incognipwn
clean:                   ## Remove local data and volumes
	docker compose down -v
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
