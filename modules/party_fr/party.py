# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool


__all__ = [
    'Party',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        # Do not display SIREN for person
        cls.siren.states = {'invisible': Bool(Eval('is_person'))}
