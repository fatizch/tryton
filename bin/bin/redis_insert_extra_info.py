#!/usr/bin/env python
import argparse
import sys

import async.broker as async_broker


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
    async_broker.set_module('celery')
    broker = async_broker.get_module()
    broker.insert_into_redis(arguments.chain, arguments.queue,
        arguments.nb_jobs, arguments.nb_records, arguments.start_time,
        arguments.duration, arguments.status)


main()
