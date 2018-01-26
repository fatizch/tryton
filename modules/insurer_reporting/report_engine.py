# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.14: Change invoice kinds
        super(ReportTemplate, cls).__register__(module_name)
        table = cls.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                columns=[table.kind],
                values=['broker_invoice'],
                where=table.kind == 'broker_report',
                ))
        cursor.execute(*table.update(
                columns=[table.kind],
                values=['insurer_invoice'],
                where=table.kind == 'insurer_report_commission',
                ))

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'insurer_report_contract': 'Insurer Report Contract',
                'insurer_report_covered': 'Insurer Report Covered',
                'insurer_invoice': 'Insurer Invoice Report',
                'broker_invoice': 'Broker Invoice Report',
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
        elif self.on_model.model == 'account.invoice':
            result.append(
                ('insurer_invoice', self.raise_user_error(
                    'insurer_invoice', raise_exception=False)))
            result.append(
                ('broker_invoice', self.raise_user_error(
                    'broker_invoice', raise_exception=False)))
        return result
