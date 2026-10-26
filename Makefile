.PHONY: up down logs test seed reseed migrate shell-db scan

up:            ## Build and start the full stack
	docker compose up --build -d

down:          ## Stop the stack (keeps data volumes)
	docker compose down

logs:          ## Follow logs for api, worker and beat
	docker compose logs -f api worker beat

test:          ## Run the backend test-suite inside Docker
	docker compose run --rm api pytest -q

migrate:       ## Apply Alembic migrations
	docker compose run --rm api alembic upgrade head

seed:          ## Load demo data if the database is empty
	docker compose run --rm api python -m app.seed

reseed:        ## Wipe all data and load fresh demo data
	docker compose run --rm api python -m app.seed --reset

scan:          ## Queue an overdue scan on the worker now
	curl -s -X POST http://localhost:8000/api/alerts/scan; echo

shell-db:      ## Open psql against the app database
	docker compose exec db psql -U cargopulse cargopulse
