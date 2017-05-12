# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields


__all__ = [
    'ContractActivate',
    'ContractActivateConfirm',
    ]


class ContractActivate:
    __metaclass__ = PoolMeta
    __name__ = 'contract.activate'

    def transition_apply(self):
        suspension_end_date = self.confirm.suspension_end_date
        if suspension_end_date:
            with ServerContext().set_context(
                    suspension_date=suspension_end_date):
                return super(ContractActivate, self).transition_apply()
        return super(ContractActivate, self).transition_apply()

    def default_confirm(self, name):
        res = super(ContractActivate, self).default_confirm(name)
        res['suspension_end_date'] = None
        return res


class ContractActivateConfirm:
    __metaclass__ = PoolMeta
    __name__ = 'contract.activate.confirm'

    suspension_end_date = fields.Date('Suspension End Date',
        help='If defined, the automatically calculated suspension end date'
        ' will be replaced')
