.DEFAULT_GOAL := help

WPI_URL ?= https://github.com/skaben/skaben/blob/master/LaserLock/wiringpi-2.32.1-py3.7-linux-armv7l.egg

.PHONY: help install config service orange-wpi clean run

help:
	@echo "Usage: make [target]"
	@echo
	@echo "Available targets:"
	@echo "  install     Install dependencies"
	@echo "  config      Create configuration files"
	@echo "  service     Install systemd service"
	@echo "  orange-wpi  Download and install WiringPi (NOT IMPLEMENTED)"
	@echo "  clean       Remove generated files"
	@echo "  run         Run the application"

install:
	sudo apt install -y libsdl2-dev libsdl2-ttf-2.0 libsdl2-ttf-dev libsdl2-image-dev libsdl2-mixer-dev
	python3.7 -m pip install --upgrade pip
	python3.7 -m pip install -r requirements.txt

config:
	mkdir -p conf resources
	chmod +x ./templates/make-conf.sh
	./templates/make-conf.sh
	tar xvf resources.tar.gz -C resources
	@echo 'Configuration created, check ./conf'

service:
	chmod +x ./templates/make-service.sh
	sh ./templates/make-service.sh
	@echo 'Service installed as /etc/systemd/system/skabenlock.service'
	systemctl status skabenlock

orange-wpi:
	@echo 'NOT IMPLEMENTED'

clean:
	rm -rf ./conf
	rm -rf ./resources

run:
	cd $(shell pwd)
	sudo python3.7 app.py
