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
                'insurer_report_contract': 'Insurer Report Contract',
                'insurer_report_covered': 'Insurer Report Covered',
                })

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'contract':
            result.append(
                ('insurer_report_contract', self.raise_user_error(
                    'insurer_report_contract', raise_exception=False)))
            result.append(
                ('insurer_report_covered', self.raise_user_error(
                    'insurer_report_covered', raise_exception=False)))
        return result
