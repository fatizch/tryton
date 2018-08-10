# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model

__all__ = [
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update(
            {
                'create_instalment_plan': {
                    'invisible': ~Eval('status').in_(['active', 'terminated'])
                    },
            })

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '/form/group[@id="instalment_buttons"]',
                'states',
                {'invisible': True}
                )]

    @classmethod
    @model.CoogView.button_action(
        'contract_instalment_plan.act_create_instalment_plan')
    def create_instalment_plan(cls, contracts):
        pass

    def get_invoice(self, start, end, billing_information):
        res = super(Contract, self).get_invoice(start, end, billing_information)
        pool = Pool()
        InstalmentPlan = pool.get('contract.instalment_plan')
        PaymentTerm = pool.get('account.invoice.payment_term')
        instalment = ServerContext().get('instalment', None)
        instalments = []
        if instalment:
            instalments = [instalment]
        else:
            instalments = InstalmentPlan.search([
                    ('state', '=', 'validated'),
                    ('contract', '=', self.id),
                    ('invoice_period_start', '<=', start),
                    ('invoice_period_end', '>=', end),
                    ])
        if instalments:
            res.instalment_plan = instalments[0]
            res.payment_term = PaymentTerm.search([
                    ('based_on_instalment', '=', True),
                    ('active', '=', True)])[0]
        return res
