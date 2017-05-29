# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields


__all__ = [
    'ContractHold',
    'ContractSelectHoldReason',
    'ContractActivate',
    'ContractActivateConfirm',
    ]


class ContractHold:
    __metaclass__ = PoolMeta
    __name__ = 'contract.hold'

    def default_select_hold_status(self, name):
        res = super(ContractHold, self).default_select_hold_status(name)
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context.get('active_ids'))
        contracts_to_hold = [contract for contract in contracts
            if contract.status == 'active']
        res['suspension_start_date'] = None
        res['show_suspension_date'] = any(x.right_suspension_allowed()
            for x in contracts_to_hold)
        return res

    def transition_apply(self):
        suspension_start_date = self.select_hold_status.suspension_start_date
        if suspension_start_date:
            with ServerContext().set_context(
                    suspension_start_date=suspension_start_date):
                return super(ContractHold, self).transition_apply()
        return super(ContractHold, self).transition_apply()


class ContractSelectHoldReason:
    __metaclass__ = PoolMeta
    __name__ = 'contract.hold.select_hold_status'

    suspension_start_date = fields.Date('Suspension Start Date', states={
            'invisible': ~Eval('show_suspension_date')},
        depends=['show_suspension_date'],
        help='If defined, the automatically calculated suspension start date'
        ' will be replaced')
    show_suspension_date = fields.Boolean('Show Suspension Date')


class ContractActivate:
    __metaclass__ = PoolMeta
    __name__ = 'contract.activate'

    def transition_apply(self):
        suspension_end_date = self.confirm.suspension_end_date
        if suspension_end_date:
            with ServerContext().set_context(
                    suspension_end_date=suspension_end_date):
                return super(ContractActivate, self).transition_apply()
        return super(ContractActivate, self).transition_apply()

    def default_confirm(self, name):
        Contract = Pool().get('contract')
        res = super(ContractActivate, self).default_confirm(name)
        active_id = Transaction().context.get('active_id')
        contract = Contract(active_id)
        res['suspension_end_date'] = None
        res['show_suspension_date'] = contract.right_suspension_allowed()
        return res


class ContractActivateConfirm:
    __metaclass__ = PoolMeta
    __name__ = 'contract.activate.confirm'

    suspension_end_date = fields.Date('Suspension End Date', states={
            'invisible': ~Eval('show_suspension_date')},
        depends=['show_suspension_date'],
        help='If defined, the automatically calculated suspension end date'
        ' will be replaced')
    show_suspension_date = fields.Boolean('Show Suspension Date')
