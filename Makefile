.DEFAULT_GOAL := help
MAKEFLAGS += -j3

UV ?= uv
NPM ?= npm
HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 3000
export API_ORIGIN ?= http://127.0.0.1:$(API_PORT)
BUSINESS_NAME ?= Usaha Saya
USERNAME ?= pemilik

DEMO_OWNER ?= demo-pemilik
DEMO_STAFF ?= demo-staf

.PHONY: help install setup seed run backend frontend worker build check

help:
	@echo StokGuard - perintah lokal
	@echo   make install    Install dependency backend dan frontend
	@echo   make setup      Buat usaha dan akun pemilik, password lewat prompt
	@echo   make seed       Buat data demo, password lewat prompt
	@echo   make run        Jalankan backend, frontend, dan worker OCR
	@echo   make backend    Jalankan API saja
	@echo   make frontend   Jalankan frontend saja
	@echo   make worker     Jalankan worker OCR saja
	@echo   make build      Build frontend produksi
	@echo   make check      Lint dan typecheck, tanpa Playwright

install:
	$(UV) sync --project backend --locked
	$(NPM) --prefix frontend ci

setup:
	$(UV) run --project backend python -m stokguard.cli setup --name "$(BUSINESS_NAME)" --username "$(USERNAME)"

seed:
	$(UV) run --project backend python -m stokguard.cli seed-demo --owner-username "$(DEMO_OWNER)" --staff-username "$(DEMO_STAFF)"

run: backend frontend worker

backend:
	$(UV) run --project backend uvicorn stokguard.main:create_app --factory --host $(HOST) --port $(API_PORT)

frontend:
	$(NPM) --prefix frontend run dev -- --hostname $(HOST) --port $(WEB_PORT)

worker:
	$(UV) run --project backend python -m stokguard.cli worker

build:
	$(NPM) --prefix frontend run build

check:
	$(UV) run --project backend ruff check backend
	$(NPM) --prefix frontend run lint
	$(NPM) --prefix frontend run typecheck
