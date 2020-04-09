.PHONY: deploy
deploy: requirements.txt
	bash scripts/deploy.sh

.PHONY: requirements.txt
requirements.txt:
	poetry export -f requirements.txt > requirements.txt

.PHONY: remote_docker
remote_docker:
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata
	docker-compose up --build -d

.PHONY: docker
docker: requirements.txt
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata
	env ALERTS_FILE=alerts.yaml docker-compose up --build
