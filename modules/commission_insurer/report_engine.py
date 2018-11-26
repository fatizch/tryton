# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'all_insurer_invoices': 'All Insurer Invoice',
                })

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'account.invoice':
            result.append(('all_insurer_invoices',
                    self.raise_user_error(
                        'all_insurer_invoices', raise_exception=False)))
        return result
