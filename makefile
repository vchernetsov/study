run-local:
	cd ./diploma/code/ && \
	jupyter notebook --NotebookApp.token='677994e03eec800990a8'


# nvidia-based reliable environment works through docker-compose + nvidia devicea available
 
compose-build:
	docker compose build

compose-up:
	docker compose up