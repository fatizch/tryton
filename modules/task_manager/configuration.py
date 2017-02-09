# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'ProcessConfiguration',
    ]


class ProcessConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'process.configuration'

    share_tasks = fields.Boolean('Share tasks among users',
        help='If true, a user will be able to instantly resume a task which '
        'was previously held by another user')
