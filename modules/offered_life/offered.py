# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval


STATE_LIFE = (
    Eval('_parent_offered', {}).get('family') != 'life')

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('life', 'Life'))
        cls.insurance_kind.selection.extend([
                ('temporary_disability', 'Temporary Disability'),
                ('partial_disability', 'Partial Disability'),
                ('total_disability', 'Total Disability'),
                ('total_autonomy_loss',
                    'Total And Irreversible Autonomy Loss'),
                ('death', 'Death'),
                ])
