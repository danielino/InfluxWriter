#!/usr/bin/env python
import os
import time
import json
import datetime
import logging
import requests
import yaml
import redis
from nameko.rpc import rpc, RpcProxy
from nameko.web.handlers import http
from nameko.timer import timer
from influxdb import InfluxDBClient
from nameko_structlog import StructlogDependency

# env configs
configFile = os.environ.get('CONFIG_FILE', 'conf/influxwriter.yml')
hostname = os.environ.get("HOSTNAME", "test")

# redis config
redisHost = os.environ.get("REDIS_HOST", "127.0.0.1")
redisPort = os.environ.get("REDIS_PORT", 6379)

# timer config
TIMER_STATS = int(os.environ.get("TIMER_STATS", 3600))
TIMER_INFLUX_PING = int(os.environ.get("TIMER_INFLUX_PING", 300))

# database configurations
with open(configFile, 'r') as configfile:
    cfg = yaml.load(configfile)

hosts = cfg['influxdb']['data']['hosts']

# define lock for queue statistics
# main function before write stats wait for unlock
QUEUE_LOCKED = False

queue = {
    "requests": 0,
    "success": 0,
    "error": 0,
}

# redis connection pool
logging.debug("redisHost: %s - redisPort: %s" % (redisHost, redisPort))
pool = redis.ConnectionPool(host=redisHost, port=redisPort)
redisPool = redis.Redis(connection_pool=pool)
redisKeys = ["influxdb_%s_%s" % (x['host'], x['port']) for x in hosts]

backends =",".join(redisKeys).replace('influxdb_', '').replace('_', ':')

class Influxwriter(object):
    name = "influxwriter"

    log = StructlogDependency()

    def clean_queue(self):
        queue['requests'] = 0
        queue['success'] = 0
        queue['error'] = 0

    def cache_error_points(self, points, host, port):
        key = "influxdb_%s_%s" % (host, port)
        self.log.debug("redis> writing message in redis queue with keys: %s" % key)
        redisPool.lpush(key, json.dumps(points))
        redisPool.save()
        self.log.debug("redis> message written")

    def influx_ping(self, uri):
        try:
            res = requests.get("http://{host}/ping".format(host=uri))
            return res.status_code == 204
        except:
            return False


    def write_points(self, points):
        self.log.debug("consume message")
        for host in hosts:
            req, success, error = (1, 0, 0)
            try:
                uri = "{host}:{port}".format(**host)
                if self.influx_ping(uri):
                    client = InfluxDBClient(**host)
                    self.log.debug("sending data to host {host}".format(host=uri))
                    try:
                        self.log.debug("influx data: %s" % str(points))
                        client.write_points(points)
                        self.log.debug("data written to host {host}".format(host=uri))
                        success = 1
                    except Exception, e:
                        self.log.error("couldn't send data %s to host %s. Exception: %s" % (points, uri, str(e)))
                        error = 1
                        raise e
                else:
                    error = 1
                    self.cache_error_points(points, host['host'], host['port'])
            except Exception, e:
                self.log.error("error. %s" % str(e))
                error = 1
                self.cache_error_points(points, host['host'], host['port'])
                raise e
            finally:
                while QUEUE_LOCKED:
                    self.log.debug("queue locked")
                    time.sleep(1)
                queue['requests'] += req
                queue['success'] += success
                queue['error'] += error

    @http("GET", "/status")
    def http_get_status(self, request):
        return json.dumps({"status" : "ok"})

    @http("POST", "/write")
    def http_write(self, request):
        self.write_points(json.loads(request.get_data(as_text=True)))

    @rpc
    def write(self, points):
        self.write_points(points)

    @timer(interval=TIMER_STATS)
    def process_stats(self):
        self.log.debug("stats--> writing message statistics")
        self.QUEUE_LOCKED = True

        points = [{
            "measurement": "messages",
            "time": datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "tags": {
                "name": "influxwriter",
                "host": hostname
            },
            "fields": queue
        }]
        try:
            self.write_points(points)
            self.clean_queue()
            self.QUEUE_LOCKED = False
        except Exception, e:
            print str(e)
            pass

    @timer(interval=TIMER_INFLUX_PING)
    def process_redis_queue(self):
        try:
            if len(redisKeys) > 0:
                # iterate available keys
                for key in redisKeys:
                    name, ip, port = key.split('_')
                    countItems = redisPool.llen(key)
                    # if redis queue length > 0
                    if countItems > 0:
                        # iterate host configs
                        for host in hosts:
                            if host['host'] == ip and int(host['port']) == int(port):
                                uri = "{host}:{port}".format(**host)
                                if self.influx_ping(uri):
                                    # iterate all items in redis queue
                                    self.log.info("align database %s:%s" % (ip, port))
                                    self.log.info("items in queue: %s" % countItems)
                                    for count in range(0, countItems):
                                        points = json.loads(redisPool.rpop(key))
                                        self.log.debug(points)
                                        self.write_points(points)
                                else:
                                    self.log.debug("-- timer -- influx not available. sleeping for %d seconds" % TIMER_INFLUX_PING)
        except Exception, e:
            self.log.error(str(e))


