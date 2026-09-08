.PHONY: install run test typecheck eval migrate web

install:
	.venv/bin/pip install -e ".[dev]" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

web:
	cd web && npm install && npm run build

run:
	.venv/bin/uvicorn app.index:app --reload --reload-dir src --host 0.0.0.0 --port 8000

typecheck:
	.venv/bin/pyrefly check src tests

test: typecheck
	.venv/bin/pytest

eval:
	.venv/bin/python -m app.eval

migrate:
	.venv/bin/alembic upgrade head
