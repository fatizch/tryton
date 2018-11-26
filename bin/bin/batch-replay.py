import sys
import coog_async.broker as async_broker


def main():
    broker = sys.argv[1]
    job_key = sys.argv[2]
    async_broker.set_module(broker)
    broker = async_broker.get_module()
    broker.replay(job_key)


if __name__ == '__main__':
    main()
