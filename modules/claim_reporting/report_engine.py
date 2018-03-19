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
                'claim_insurer_report': 'Insurer Report Claim',
                })

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'claim.service':
            result.append(
                ('claim_insurer_report', self.raise_user_error(
                    'claim_insurer_report', raise_exception=False)))
        return result