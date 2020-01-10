# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby

from trytond.pool import Pool, PoolMeta


__all__ = [
    'InvoiceSlipConfiguration',
    ]


class InvoiceSlipConfiguration(metaclass=PoolMeta):

    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _finalize_invoice_lines(cls, slip_parameters, account_data):
        super(InvoiceSlipConfiguration, cls)._finalize_invoice_lines(
            slip_parameters, account_data)
        for slip_parameter in slip_parameters:
            cls._add_wholesale_broker_invoice_line(slip_parameter,
                account_data)

    @classmethod
    def get_wholesale_brokers_line_domain(cls, account, party, until_date):
        domain = [
            ('account', '=', account.id),
            ('principal_invoice_line', '=', None),
            ('journal.type', '=', 'commission'),
            ('party', '!=', party.id),
            ('origin.id', '!=', None, 'account.invoice')
            ]
        if until_date:
            domain.append(('date', '<=', until_date))
        return domain

    @classmethod
    def get_wholesale_brokers_line(cls, amount, account, party):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        line = Line()
        line.type = 'line'
        line.quantity = 1
        line.unit_price = amount
        line.account = account
        line.description = cls.raise_user_error(
            'wholesale_broker_reimbursement', party.rec_name,
            raise_exception=False)
        return line

    @classmethod
    def _add_wholesale_broker_invoice_line(cls, slip_parameter, account_data):
        pool = Pool()
        Line = pool.get('account.move.line')

        commission_invoice = account_data['invoice']
        for account in slip_parameter['accounts']:
            lines = Line.search(
                cls.get_wholesale_brokers_line_domain(account,
                    commission_invoice.party, commission_invoice.invoice_date),
                order=[('party', 'ASC')])
            if not lines:
                continue
            for party, party_lines in groupby(
                    lines, key=lambda x: x.party):
                amount = sum(-l.amount for l in lines)
                invoice_line = cls.get_wholesale_brokers_line(
                    amount, account, party)
                invoice_line.invoice = commission_invoice
                invoice_line.save()
                Line.write(list(party_lines), {
                        'principal_invoice_line': invoice_line.id,
                        })
