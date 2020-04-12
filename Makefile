define compose
	docker-compose --file "$(1)"
endef

define compose-api
	$(call compose,api/docker-compose.yaml)
endef

define compose-cli
	$(call compose,cli/docker-compose.yaml)
endef

define compose-mormo
	$(compose-api) --file api/mormo/docker-compose.yaml
endef

define dcgoss-cli
	cd cli/ && dcgoss $(1) signal_alerts_cli
endef

define dcgoss-api
	cd api/ && dcgoss $(1) signal_alerts_api
endef

DOCKER_HOST =	$(shell docker network inspect bridge -f "{{(index .IPAM.Config 0).Gateway}}")

.PHONY: signal_data
signal_data:
	docker volume inspect signaldata 2>/dev/null | docker volume create signaldata

.PHONY: deploy
deploy: requirements.txt
	bash scripts/deploy.sh

.PHONY: requirements.txt
requirements.txt:
	poetry export -f requirements.txt > requirements.txt

.PHONY: docker_cli
docker_cli: signal_data
	env HOSTNAME=$(shell hostname)-signal_alerts_cli $(compose-cli) up --build -d

.PHONY: docker_api
docker_api: signal_data
	env HOSTNAME=$(shell hostname)-signal_alerts_api $(compose-api) up --build -d

.PHONY: mormo_test
mormo_test:
	cd api/mormo\
		&& mormo test -c api_mormo.yaml -t http://localhost:8000/openapi.json -v

.PHONY: docker_mormo_test
docker_mormo_test: signal_data
	env MORMO_FILE=api_mormo.yaml MORMO_HOST=http://$(DOCKER_HOST):8000 $(compose-mormo) up --build --abort-on-container-exit

.PHONY: test_against_mormo_api
test_against_mormo_api:
	cd api/mormo\
		&& python3 ../../scripts/api_client.py --test_config api_mormo.yaml --target http://localhost:8000/openapi.json --mormo_api ${MORMO_API:-http://localhost:8001} --verbose

.PHONY: dcgoss_cli_edit
dcgoss_cli_edit:
	$(call dcgoss-cli,edit)

.PHONY: test_docker_cli
test_docker_cli:
	$(call dcgoss-cli,run)

.PHONY: dcgoss_api_edit
dcgoss_api_edit:
	$(call dcgoss-api,edit)

.PHONY: test_docker_api
test_docker_api:
	$(call dcgoss-api,run)
