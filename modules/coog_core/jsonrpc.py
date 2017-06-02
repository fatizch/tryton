# This file is part of Coog.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import pickle
import types

from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.pool import PoolMeta, Pool


__all__ = [
    'PoolObjectEncoder',
    'PoolObjectDecoder',
    ]


class PoolObjectEncoder(JSONEncoder):
    def default(self, obj):
        """
        This decoder handles trytond Model instances,
        simple functions (not nested functions or functions with nested
        functions) and simple classmethods from tryton models.
        """
        if hasattr(obj, '__metaclass__') and issubclass(obj.__metaclass__,
                PoolMeta):
            return {'__pool__': True, 'data': str(obj)}
        elif isinstance(obj, types.FunctionType):
            return {'__function__': True, 'data': pickle.dumps(obj)}
        elif isinstance(obj, types.MethodType):
            return {'__method__': True, 'data': '%s,%s' % (
                    obj.im_class.__name__, obj.__name__)}
        return super(PoolObjectEncoder, self).default(obj)


class PoolObjectDecoder(JSONDecoder):
    def default(self, obj):
        pool = Pool()
        if isinstance(obj, dict) and '__pool__' in obj.keys():
            model_name, id_ = obj['data'].split(',')
            return pool.get(model_name, type='*')(eval(id_))
        elif isinstance(obj, dict) and '__function__' in obj.keys():
            return pickle.loads(obj['data'])
        elif isinstance(obj, dict) and '__method__' in obj.keys():
            model_name, method_name = obj['data'].split(',')
            return getattr(pool.get(model_name, type='*'), method_name)
        return super(PoolObjectDecoder, self).default(obj)
