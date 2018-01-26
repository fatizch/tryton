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
        if isinstance(obj.__class__, PoolMeta) or \
                obj.__class__.__name__ == 'TranslateModel':
            # JMO: The ligne above is a workaround for cases, in python3,
            # where obj is an instance of TranslateModel,
            # but not of type PoolMeta
            return {'__pool__': True, 'data': str(obj)}
        elif isinstance(obj, types.FunctionType):
            return {'__function__': True, 'data': pickle.dumps(obj)}
        elif isinstance(obj, types.MethodType):
            return {'__method__': True, 'data': '%s,%s' % (
                    obj.im_class.__name__, obj.__name__)}
        return super(PoolObjectEncoder, self).default(obj)


class PoolObjectDecoder(JSONDecoder):

    def __call__(self, obj_):
        if isinstance(obj_, dict) and '__pool__' in obj_.keys():
            model_name, id_ = obj_['data'].split(',')
            return Pool().get(model_name)(eval(id_))
        elif isinstance(obj_, dict) and '__function__' in obj_.keys():
            return pickle.loads(obj_['data'])
        elif isinstance(obj_, dict) and '__method__' in obj_.keys():
            model_name, method_name = obj_['data'].split(',')
            return getattr(Pool().get(model_name), method_name)
        return super(PoolObjectDecoder, self).__call__(obj_)
