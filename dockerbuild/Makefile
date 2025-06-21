.PHONY: local run update

VERSION := 1.0.1 
TAG := wyoming-google
PLATFORMS := linux/amd64,linux/arm64
#,linux/armv7
DATA_DIR := ${HOME}/wyoming-google/config
MODEL_LANG := en
HOST := 0.0.0.0
PORT := 10555

all:
	docker buildx build . --platform "$(PLATFORMS)" --tag "$(TAG):$(VERSION)" --push
#	docker buildx create --name multiarch --driver docker-container --use

update:
	docker buildx build . --platform "$(PLATFORMS)" --tag "$(TAG):latest" --push

local:
	docker build . -t "$(TAG):$(VERSION)" --build-arg TARGETARCH=amd64

run:
	docker run -it -p $(PORT):$(PORT) -v $(DATA_DIR):/config $(TAG):$(VERSION) --debug
	
	
