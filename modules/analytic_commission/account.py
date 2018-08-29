# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql.aggregate import Sum
from sql.functions import ToChar

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__all__ = [
    'Account',
    'Configuration',
    ]


class Account:
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.account'

    def distribute_over_extra_details(self, amount):
        invoice_line = ServerContext().get('invoice_line', None)
        assert invoice_line

        return_list = []

        handle_signature_date, handle_product, handle_broker = \
            False, False, False

        extra_details_keys = sorted(list(
                set(x.name for x in self.pattern.lines)))
        # The keys are in alphabetic order, which allows correspondence in zip
        # below
        handle_signature_date = ('commissioned_contract_signature_month' in
            extra_details_keys)
        handle_product = 'commissioned_contract_product' in extra_details_keys
        handle_broker = 'commissioned_contract_broker' in extra_details_keys

        pool = Pool()
        contract = pool.get('contract').__table__()
        commission = pool.get('commission').__table__()
        account_invoice_line = pool.get('account.invoice.line').__table__()

        cursor = Transaction().connection.cursor()

        tables = account_invoice_line.join(commission,
            condition=(account_invoice_line.id == commission.invoice_line))
        columns = [Sum(commission.amount)]
        group_by_columns = []

        if handle_signature_date or handle_product or handle_broker:
            tables = tables.join(contract,
                condition=(contract.id == commission.commissioned_contract))

        if handle_broker:
            columns.append(contract.agent)
            group_by_columns.append(contract.agent)
        if handle_product:
            columns.append(contract.product)
            group_by_columns.append(contract.product)
        if handle_signature_date:
            columns.append(
                ToChar(contract.signature_date, 'YYYYMM').as_('month_year'))
            group_by_columns.append(ToChar(contract.signature_date, 'YYYYMM'))

        query = tables.select(*columns,
            where=(account_invoice_line.id == invoice_line.id),
            group_by=group_by_columns)

        cursor.execute(*query)

        for result in cursor.fetchall():
            amount = Decimal(result[0]).quantize(
                Decimal(10) ** -self.currency_digits)
            extra_details = {}
            if len(result) > 1:
                for key, detail in zip(extra_details_keys, result[1:]):
                    extra_details[key] = detail
            return_list.append((self, amount, extra_details))
        return return_list


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    broker_analytic_account_to_use = fields.Many2One('analytic_account.account',
        'Broker Analytic Account To Use')
