
default:
    @just --list

# Install poetry locally
install:
    poetry install

# Start project in development mode with autoreload
dev:
    docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build


# Run tests in docker
test:
    docker compose run --build --rm api pytest -vv .
    docker compose down

# Run the agent-to-agent API demo against a running local API.
demo-a2a:
    python scripts/a2a_demo.py

# pulls from repo
pull:
    git pull

# pull run
go: pull dev
