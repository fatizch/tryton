# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields

__all__ = [
    'PaymentTerm',
    ]


class PaymentTerm:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.payment_term'

    based_on_instalment = fields.Boolean('Based On Instalment Plan',
        help='If checked, the terms will be calculated to match the entered '
        'instalment plan.')

    @classmethod
    def __setup__(cls):
        super(PaymentTerm, cls).__setup__()
        cls._error_messages.update({
                'no_invoice_provided': ('A contract invoice with an instalment '
                    'is required to compute terms based on instalment.'),
                })
        cls.lines.states.update({'invisible': Eval('based_on_instalment')})

    @staticmethod
    def default_based_on_instalment():
        return False

    def check_remainder(self):
        if not self.based_on_instalment:
            super(PaymentTerm, self).check_remainder()

    def compute(self, amount, currency, date=None):
        if not self.based_on_instalment:
            return super(PaymentTerm, self).compute(amount, currency, date)
        invoice = ServerContext().get('_current_invoice', None)
        if not invoice:
            self.raise_user_error('no_invoice_provided')
        instalment = invoice.instalment_plan
        if not instalment:
            self.raise_user_error('no_invoice_provided')
        contract = instalment.contract
        start_date = invoice.start
        end_date = invoice.end
        if not start_date or not end_date:
            self.raise_user_error('no_invoice_provided')
        previous_invoices = contract.get_future_invoices(contract,
            instalment.invoice_period_start,
            start_date + relativedelta(days=-1))
        scheduled_payments = [[x.maturity_date, x.amount]
            for x in instalment.scheduled_payments]
        i = 0
        for invoice in previous_invoices:
            invoice_amount = invoice.get('total_amount', 0.0)
            while invoice_amount != 0:
                if scheduled_payments[i][1] > invoice_amount:
                    scheduled_payments[i][1] -= invoice_amount
                    invoice_amount = 0
                else:
                    invoice_amount -= scheduled_payments[i][1]
                    scheduled_payments[i][1] = 0
                    i += 1
        res = []
        remainder = -amount
        for x in scheduled_payments[i:]:
            if x[1] < remainder:
                res.append((x[0], -x[1]))
                remainder -= x[1]
            else:
                res.append((x[0], -remainder))
                remainder = 0
                break
        if remainder:
            res.append((scheduled_payments[-1][0], -remainder))
        return res
