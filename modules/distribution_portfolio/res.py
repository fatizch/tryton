# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'User',
    ]


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._context_fields.append('dist_network')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('dist_network')
        return result
