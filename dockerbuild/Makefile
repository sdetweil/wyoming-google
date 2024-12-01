.PHONY: local run update

VERSION := 1.0.0
TAG := rhasspy/wyoming-google
PLATFORMS := linux/amd64,linux/arm64
#,linux/armv7
DATA_DIR := ${HOME}/wyoming-google/config
MODEL_LANG := en
HOST := 0.0.0.0
PORT := 10555

all:
	docker buildx build . --platform "$(PLATFORMS)" --tag "$(TAG):$(VERSION)" --load
#	docker buildx create --name multiarch --driver docker-container --use

update:
	docker buildx build . --platform "$(PLATFORMS)" --tag "$(TAG):latest" --load

local:
	docker buildx build . -t "$(TAG):$(VERSION)" --build-arg TARGETARCH=amd64 --load
run:
	docker run -it -p $(PORT):$(PORT) -v $(DATA_DIR):/config $(TAG):$(VERSION) --debug
	
	
