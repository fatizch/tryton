# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    @classmethod
    def __register__(cls, module_name):
        super(OptionDescription, cls).__register__(module_name)
        # Migration from 1.8: Drop Salary Range
        TableHandler = backend.get('TableHandler')
        if TableHandler.table_exist('salary_range'):
            TableHandler.drop_table('salary_range.version',
                'salary_range_version', True)
            TableHandler.drop_table('salary_range', 'salary_range', True)

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
                ('education_annuities', 'Education Annuities'),
                ('joint_annuities', 'Joint Annuities'),
                ('funeral_capital', 'Funeral Capital'),
                ('death', 'Death'),
                ])
