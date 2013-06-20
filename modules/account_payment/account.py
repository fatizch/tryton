#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.backend import FIELDS

from .payment import KINDS

__metaclass__ = PoolMeta
__all__ = ['MoveLine']


class MoveLine:
    __name__ = 'account.move.line'
    payment_amount = fields.Function(fields.Numeric('Payment Amount',
            digits=(16,
                If(Bool(Eval('second_currency_digits')),
                    Eval('second_currency_digits', 2),
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('payment_kind'),
                },
            depends=['payment_kind']), 'get_payment_amount',
        searcher='search_payment_amount')
    payments = fields.One2Many('account.payment', 'line', 'Payments',
        readonly=True,
        states={
            'invisible': ~Eval('payment_kind'),
            },
        depends=['payment_kind'])
    payment_kind = fields.Function(fields.Selection([
                (None, ''),
                ] + KINDS, 'Payment Kind'), 'get_payment_kind',
        searcher='search_payment_kind')

    @classmethod
    def get_payment_amount(cls, lines, name):
        amounts = {}
        for line in lines:
            if line.account.kind not in ('payable', 'receivable'):
                amounts[line.id] = None
                continue
            if line.second_currency:
                if line.debit - line.credit > 0:
                    amount = abs(line.amount_second_currency)
                else:
                    amount = -abs(line.amount_second_currency)
            else:
                amount = line.credit - line.debit

            for payment in line.payments:
                if payment.state != 'failed':
                    if payment.kind == 'payable':
                        amount -= payment.amount
                    else:
                        amount += payment.amount

            if line.account.kind == 'receivable' and amount != 0:
                amount *= -1
            amounts[line.id] = amount
        return amounts

    @classmethod
    def search_payment_amount(cls, name, clause):
        pool = Pool()
        cursor = Transaction().cursor
        Payment = pool.get('account.payment')
        Account = pool.get('account.account')
        _, operator, value = clause
        assert operator in ('=', '!=', '<=', '>=', '<', '>')
        cursor.execute('SELECT l.id FROM "' + cls._table + '" AS l '
            'LEFT JOIN "' + Payment._table + '" AS p '
                'ON l.id = p.line '
            'JOIN "' + Account._table + '" AS a '
                'ON l.account = a.id '
            'WHERE a.kind IN (\'payable\', \'receivable\') '
                'AND (p.id IS NULL OR p.state != \'failed\') '
            'GROUP BY l.id, a.kind, l.second_currency '
            'HAVING CASE WHEN l.second_currency IS NULL '
                'THEN '
                    'CASE WHEN a.kind = \'payable\' '
                    'THEN (l.credit - l.debit)  - SUM('
                        'CASE WHEN p.id > 0 THEN p.amount ELSE 0.0 END) '
                    'ELSE (l.debit - l.credit ) - SUM('
                        'CASE WHEN p.id > 0 THEN p.amount ELSE 0.0 END) '
                    'END '
                'ELSE '
                    'CASE WHEN a.kind = \'payable\' '
                    'THEN (l.amount_second_currency '
                        '* ABS(l.debit - l.credit) / (l.debit - l.credit)) '
                        '- SUM(p.amount) '
                    'ELSE (l.amount_second_currency '
                        ' * ABS(l.credit - l.debit) / (l.credit - l.debit)) '
                        '- SUM(p.amount) '
                    'END '
                'END ' + operator + ' %s',
            (FIELDS[cls.payment_amount._type].sql_format(value),))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_payment_kind(self, name):
        return self.account.kind if self.account.kind in dict(KINDS) else None

    @classmethod
    def search_payment_kind(cls, name, clause):
        return [('account.kind',) + tuple(clause[1:])]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('payments', None)
        return super(MoveLine, cls).copy(lines, default=default)
