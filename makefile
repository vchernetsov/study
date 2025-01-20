# http://127.0.0.1:8889/tree?token=677994e03eec800990a8
local:
	cd ./diploma/code/ && \
	jupyter notebook --NotebookApp.token='677994e03eec800990a8'

# nvidia-based reliable environment works through docker-compose + nvidia devices available
build:
	docker compose build

up:
	docker compose up

bash:
	docker exec -it study-tensorflow-gpu-1 bash

shell:
	docker exec -it study-tensorflow-gpu-1 python