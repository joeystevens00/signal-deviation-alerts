define compose
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata
	docker-compose --file "$(1)" up --build -d
endef

DOCKER_HOST =	$(shell docker network inspect bridge -f "{{(index .IPAM.Config 0).Gateway}}")

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
	env HOSTNAME=$(shell hostname)-signal_alerts_cli $(call compose,cli/docker-compose.yaml)
	#env ALERTS_FILE=alerts.yaml docker-compose --file cli/docker-compose.yaml up --build

.PHONY: docker_api
docker_api: requirements.txt
	env HOSTNAME=$(shell hostname)-signal_alerts_api $(call compose,api/docker-compose.yaml)

.PHONY: mormo_test
mormo_test:
	curl http://localhost:8000/openapi.json > openapi.json
	mormo run -t api_mormo.yaml -i openapi.json -o /tmp/matrix_logger_mormo.json --test --host http://localhost:8000 --verbose

.PHONY: signal_data
signal_data:
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata

.PHONY: docker_mormo_test
docker_mormo_test: signal_data
	env MORMO_FILE=api_mormo.yaml MORMO_HOST=http://$(DOCKER_HOST):8000 docker-compose --file api/docker-compose.yaml --file api/mormo/docker-compose.yaml up --build --abort-on-container-exit
