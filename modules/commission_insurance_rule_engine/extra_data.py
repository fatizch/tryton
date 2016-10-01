# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta

__all__ = [
    'ExtraData',
    'CommissionPlanExtraDataRelation',
    ]


class ExtraData:
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('agent', 'Agent'))


class CommissionPlanExtraDataRelation(model.CoogSQL):
    'Relation between Commission Plan and Extra Data'

    __name__ = 'commission-plan-extra_data'

    plan = fields.Many2One('commission.plan', 'Commission Plan',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')
