define compose
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata
	docker-compose --file "$(1)" up --build -d
endef

.PHONY: deploy
deploy: requirements.txt
	bash scripts/deploy.sh

.PHONY: requirements.txt
requirements.txt:
	poetry export -f requirements.txt > requirements.txt

.PHONY: remote_docker_cli
remote_docker_cli:
	$(call compose,cli/docker-compose.yaml)

.PHONY: docker_cli
docker_cli: requirements.txt
	$(call compose,cli/docker-compose.yaml)
	#env ALERTS_FILE=alerts.yaml docker-compose --file cli/docker-compose.yaml up --build

.PHONY: docker_api
docker_api: requirements.txt
	$(call compose,api/docker-compose.yaml)
