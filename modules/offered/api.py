# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core.api import APIResourceMixin


__all__ = [
    'ExtraData',
    ]


class ExtraData(APIResourceMixin, metaclass=PoolMeta):
    __name__ = 'extra_data'
