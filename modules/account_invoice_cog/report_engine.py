# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__all__ = [
    'ReportTemplate',
    ]


class ReportTemplate(metaclass=PoolMeta):
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

    def get_possible_kinds(self):
        result = super(ReportTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if self.on_model.model == 'account.invoice':
            result.append(
                ('contract_invoice',
                    gettext('account_invoice_cog.msg_contract_invoice')))
        return result
