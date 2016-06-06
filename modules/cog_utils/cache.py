
from trytond.transaction import Transaction
from trytond.cache import LRUDict
from trytond.config import config

__all__ = [
    'CoogCache',
    ]

CACHE_SIZE_LIMIT = config.get('cache', 'coog_cache_size')


class CoogCache(LRUDict):
    def __init__(self, size_limit=CACHE_SIZE_LIMIT, *args, **kwargs):
        super(CoogCache, self).__init__(size_limit, *args, **kwargs)


def get_cache_holder():
    # this cache is owned by the Transaction. So it is thread safe.
    transaction_cache = Transaction().cache
    coog_cache = transaction_cache.get('__coog__', None)
    if coog_cache is None:
        coog_cache = CoogCache()
        transaction_cache['__coog__'] = coog_cache
    return coog_cache
