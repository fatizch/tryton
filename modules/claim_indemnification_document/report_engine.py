# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'claim_invoice': 'Claim Invoice',
                })

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'account.invoice':
            result.append(('claim_invoice',
                    self.raise_user_error(
                        'claim_invoice', raise_exception=False)))
        return result
