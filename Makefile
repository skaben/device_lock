.EXPORT_ALL_VARIABLES:
WPI_EGG ?= wiringpi-2.32.1-py3.7-linux-armv7l.egg
WPI_URL ?= https://github.com/skaben/skaben/blob/master/LaserLock/


.PHONY: install
install:
	@sudo apt install -y libsdl2-dev libsdl2-ttf-2.0 libsdl2-ttf-dev libsdl2-image-dev libsdl2-mixer-dev
	@python3.7 -m pip install --upgrade pip
	@python3.7 -m pip install -r requirements.txt

.PHONY: config
config:
	@mkdir conf resources
	@chmod +x ./templates/make-conf.sh
	@./templates/make-conf.sh
	@tar xvf resources.tar.gz
	@echo 'config created, check ./conf'

.PHONY: orange-wpi
orange-wpi:
	@echo 'NOT IMPLEMENTED'
	#@wget ${WPI_URL}${WPI_EGG}
	#@sudo python3.7 -m easy_install ${WPI_EGG}


.PHONY: clean
clean:
	@rm -rf ./conf
	@rm -rf ./resources	

