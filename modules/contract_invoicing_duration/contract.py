# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields
from trytond.pyson import Eval
from trytond.exceptions import UserError

__all__ = [
    'Contract'
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    invoicing_end_date = fields.Date('Invoicing end date', readonly=True,
        states={'invisible': ~Eval('invoicing_end_date')},
        help='If set, invoices will be generated until this date')

    def init_invoicing_end_date(self):
        if self.product.billing_rules:
            args = {}
            self.init_dict_for_rule_engine(args)
            invoicing_end_date = self.product.billing_rules[0].\
                calculate_invoicing_end_rule(args)
            if invoicing_end_date and \
                    invoicing_end_date < self.initial_start_date:
                raise UserError(gettext('contract_invoicing_duration.'
                    'msg_invalid_invoicing_end_date'))
            self.invoicing_end_date = invoicing_end_date

    @classmethod
    def _calculate_methods(cls, product):
        return [('contract', 'init_invoicing_end_date')] + \
            super(Contract, cls)._calculate_methods(product)

    def _calculate_final_invoice_end_date(self):
        end_date = super()._calculate_final_invoice_end_date()
        if self.invoicing_end_date:
            return min(filter(None, [end_date, self.invoicing_end_date]))
        return end_date
