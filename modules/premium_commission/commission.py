from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'CommissionPlan',
    'CommissionPlanFee',
    ]


class CommissionPlan:
    __name__ = 'commission.plan'

    fees = fields.Many2Many('commission.plan-account.fee', 'plan', 'fee',
        'Fees')


class CommissionPlanFee(model.CoopSQL):
    'Commission Plan Fee'

    __name__ = 'commission.plan-account.fee'

    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)
    plan = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE',
        required=True)
