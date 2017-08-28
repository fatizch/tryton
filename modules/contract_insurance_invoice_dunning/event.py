# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Cast
from sql.functions import Substring, Position

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    ]


class EventLog:
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if object_.__name__ != 'account.dunning' or model_name != 'contract':
            return super(EventLog, cls).get_related_instances(object_,
                model_name)
        return [object_.contract]
