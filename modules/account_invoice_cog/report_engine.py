# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.14: Change invoice kinds
        table = cls.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                columns=[table.kind],
                values=['contract_invoice'],
                where=table.kind == 'base_invoice_report',
                ))

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'contract_invoice': 'Contract Invoice',
                })

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'account.invoice':
            result.append(
                ('contract_invoice', self.raise_user_error(
                    'contract_invoice', raise_exception=False)))
        return result
