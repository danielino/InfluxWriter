
build-base: 
	docker build -t namekopy2:latest nameko

build-influxwriter:
	docker build -t influxwriter:latest .


all: build-base build-influxwriter
