import sys
import async.broker_rq as broker
from tryton_test import test
from doc_generation import generate


def main():
    modules = sys.argv[1:]
    for module in modules:
        broker.enqueue('test', test, (module,))
    broker.enqueue('test', generate, ('documentation generation',))


if __name__ == '__main__':
    main()
