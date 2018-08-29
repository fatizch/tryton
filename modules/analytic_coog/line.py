# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core.extra_details import WithExtraDetails

__all__ = [
    'Line',
    ]


class Line(WithExtraDetails):
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.line'
