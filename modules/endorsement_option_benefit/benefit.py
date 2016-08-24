# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'OptionBenefit',
    ]


class OptionBenefit:
    __metaclass__ = PoolMeta

    __name__ = 'contract.option.benefit'
    _history = True
