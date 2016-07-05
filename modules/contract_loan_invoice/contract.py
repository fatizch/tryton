# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And, Or, Not, In

from trytond.modules.cog_utils import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ExtraPremium',
    'Premium',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_show_all_invoices': {},
                })

    @classmethod
    def load_from_cached_invoices(cls, cache):
        invoices = super(Contract, cls).load_from_cached_invoices(cache)
        loan_ids = cache['loan_ids']
        if loan_ids:
            Loan = Pool().get('loan')
            loan_per_id = {x.id: x for x in Loan.browse(loan_ids)}
            for invoice in invoices:
                for line in invoice['details']:
                    if line['loan'] is None:
                        continue
                    line['loan'] = loan_per_id[line['loan']]
        return invoices

    @classmethod
    def dump_to_cached_invoices(cls, future_invoices):
        cached = super(Contract, cls).dump_to_cached_invoices(future_invoices)
        loan_ids = set([])
        for invoice in cached['invoices']:
            for line in invoice['details']:
                if line['loan'] is not None:
                    line['loan'] = line['loan'].id
                    loan_ids.add(line['loan'])
        cached['loan_ids'] = list(loan_ids)
        return cached

    def new_future_invoice(self, contract_invoice):
        invoice = super(Contract, self).new_future_invoice(contract_invoice)
        invoice['loan'] = None
        return invoice

    def set_future_invoice_lines(self, contract_invoice, displayer):
        super(Contract, self).set_future_invoice_lines(contract_invoice,
            displayer)
        for detail in displayer['details']:
            detail['loan'] = detail['premium'].loan

    @classmethod
    @model.CoopView.button_action(
        'contract_loan_invoice.act_show_all_invoices')
    def button_show_all_invoices(cls, contracts):
        pass


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls.flat_amount_frequency.states['invisible'] = And(
            cls.flat_amount_frequency.states['invisible'],
            Not(In(Eval('calculation_kind', ''), ['initial_capital_per_mil',
                        'remaining_capital_per_mil'])))
        cls.flat_amount_frequency.states['required'] = Or(
            cls.flat_amount_frequency.states['required'],
            In(Eval('calculation_kind', ''), ['initial_capital_per_mil',
                    'remaining_capital_per_mil']))


class Premium:
    __name__ = 'contract.premium'

    loan = fields.Many2One('loan', 'Loan', select=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        # Make sure premiums are properly ordered per loan
        cls._order.insert(0, ('loan', 'ASC'))

    def duplicate_sort_key(self):
        key = super(Premium, self).duplicate_sort_key()
        return tuple([self.loan.id if self.loan else None] + list(key))

    def same_value(self, other):
        return super(Premium, self).same_value(other) and (
            self.loan == other.loan)

    @classmethod
    def new_line(cls, line, start_date, end_date):
        if isinstance(line.rated_instance, Pool().get('loan.share')):
            line.rated_instance = line.rated_instance.option
        result = super(Premium, cls).new_line(line, start_date, end_date)
        result.loan = line.loan
        return result

    def _get_key(self, no_date=False):
        key = super(Premium, self)._get_key(no_date=no_date)
        return (self.loan,) + key
