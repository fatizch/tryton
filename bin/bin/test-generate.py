import sys
import async.broker_rq as broker
from tryton_test import test


def main():
    modules = sys.argv[1:]
    for module in modules:
        broker.enqueue('test', test, (module,))


if __name__ == '__main__':
    main()
