## InfluxWriter

this software replicate write to many influxdb backend database.


Requirements:

- RedisDB
- RabbitMQ
- InfluxDB

## Description

write can be sent as rabbitmq message or by http post request


## RabbitMQ message

@@TODO


## HTTP Post Request

- http payload application/json

```
[
  {
    "measurement" : "test",
    "tags" : {
      "source" : "postman"
    },
    "fields" : {
      "value": 10.1
    }
  }	
]
```

## Configuration

to configure the influxdb backend database, you can modify conf/influxwriter.yml

```yaml
influxdb:
  data:
    hosts:
      - host: influxdb
        port: 8086
        username: influxdb
        password: influxdb
        database: mydb
      - host: xxx
        port: yyy
        ...
```

## Deploy

docker-compose provide:

- chronograf container to explore data at http://localhost:8888
- rabbitmq management plugin http://localhost:15678

```bash
# make all
# docker-compose up -d
```
