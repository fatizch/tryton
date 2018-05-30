# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Benefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'
    prest_ij = fields.Boolean('Handle Prest IJ System',
        help='If set, the claims declared using this benefit will be handled '
        'by the Prest IJ system')
