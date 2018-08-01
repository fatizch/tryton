#!/usr/bin/env python
import os
import redis
import argparse
import sys
import json

from urlparse import urlparse

broker_url = os.environ.get('TRYTOND_ASYNC_CELERY')
assert broker_url, 'TRYTOND_ASYNC_CELERY should be set'
broker_url = urlparse(broker_url)
broker_host = broker_url.hostname
broker_port = broker_url.port
broker_db = broker_url.path.strip('/')


def insert_into_redis(chain, queue, nb_jobs, nb_records, start_time,
        duration, status):
    connection = redis.StrictRedis(host=broker_host, port=broker_port,
        db=broker_db)
    info = {
        "chain_name": chain,
        "queue": queue,
        "nb_jobs": nb_jobs,
        "nb_records": nb_records,
        "first_launch_date": start_time,
        "duration_in_sec": duration,
        "status": status
    }
    info_s = json.dumps(info)
    connection.set("coog:extra:" + chain + queue + start_time, info_s)


def check_integer(string):
    try:
        int(string)
        return True
    except ValueError:
        return False


def check_arguments_format(arguments):
    res = True
    if not check_integer(arguments.nb_jobs):
        sys.stderr.write("Nb Jobs must be an integer\n")
        res = False
    if not check_integer(arguments.nb_records):
        sys.stderr.write("Nb Records must be an integer\n")
        res = False
    if not check_integer(arguments.duration):
        sys.stderr.write("Duration must be an integer\n")
        res = False
    # check date format
    return res


def main():
    parser = argparse.ArgumentParser(
        description='Coog utils to insert batch additonal information in Redis')
    parser.add_argument('--chain', '-c', help='Chain Name', default=' ')
    parser.add_argument('--queue', '-q', required=True, help='Queue Name')
    parser.add_argument('--nb_jobs', '-j', help='Nb Jobs', default="1")
    parser.add_argument('--nb_records', '-r', help='Nb Records', default="1")
    parser.add_argument('--start_time', '-s', help='Start Time')
    parser.add_argument(
        '--duration', '-d', help='Duration in seconds', default="0")
    parser.add_argument(
        '--status', '-st', help='Status', default="pending")
    arguments = parser.parse_args()
    if not check_arguments_format(arguments):
        exit(1)
    insert_into_redis(arguments.chain, arguments.queue, arguments.nb_jobs,
        arguments.nb_records, arguments.start_time, arguments.duration,
        arguments.status)


main()
