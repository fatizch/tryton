from trytond.pool import PoolMeta

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'CommissionPlan',
    'CommissionPlanFee',
    'Agent',
    'AgentFee',
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


class Agent:
    __name__ = 'commission.agent'

    fees = fields.Many2Many('commission.agent-account.fee', 'agent', 'fee',
        'Fees')


class AgentFee(model.CoopSQL):
    'Agent Fee'

    __name__ = 'commission.agent-account.fee'

    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        required=True)
    agent = fields.Many2One('commission.agent', 'Agent', ondelete='CASCADE',
        required=True)
