# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ReportTemplate',
    'ReportGenerate',
    ]


class ReportTemplate:
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if self.on_model and self.on_model.model == 'document.request':
            result.append(('doc_request', 'Document Request'))
        return result


class ReportGenerate:
    __name__ = 'report.generate'

    @classmethod
    def get_context(cls, records, data):
        context = super(ReportGenerate, cls).get_context(records, data)
        context['force_remind'] = Transaction().context.get('force_remind', False)
        return context
