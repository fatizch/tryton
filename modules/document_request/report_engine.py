# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__all__ = [
    'ReportGenerate',
    ]


class ReportGenerate:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate'

    @classmethod
    def get_context(cls, records, data):
        context = super(ReportGenerate, cls).get_context(records, data)
        context['force_remind'] = Transaction().context.get('force_remind',
            True)
        return context
