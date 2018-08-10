# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or, Bool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, model

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    instalment_plan = fields.Many2One('contract.instalment_plan',
        'Instalment Plan', states={'invisible': ~Eval('instalment_plan'),
            'readonly': Eval('state') != 'draft'},
        depends=['state'], ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude.append('instalment_plan')
        cls.payment_term.states.update({'invisible': Eval('instalment_plan')})
        cls._buttons.update(
            {
                'create_instalment_plan_from_invoices': {
                    'invisible': Or(
                        Bool(Eval('instalment_plan')),
                        Bool(~Eval('contract')))
                    },
            })

    def get_move(self):
        with ServerContext().set_context(_current_invoice=self):
            return super(Invoice, self).get_move()

    @classmethod
    @model.CoogView.button_action(
        'contract_instalment_plan.act_create_instalment_plan_from_invoices')
    def create_instalment_plan_from_invoices(cls, invoices):
        pass
