# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'contract':
            result.append(
                ('insurer_report_contract',
                    gettext('insurer_reporting.msg_insurer_report_contract')))
            result.append(
                ('insurer_report_covered',
                    gettext('insurer_reporting.msg_insurer_report_covered')))
        return result
