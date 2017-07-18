# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import model, fields

__all__ = [
    'Benefit',
    'BenefitDependencyRelation',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    sub_benefits = fields.Many2Many('benefit-benefit', 'master', 'slave',
        'Sub Benefits')
    parent_benefits = fields.Many2Many('benefit-benefit', 'slave', 'master',
        'Parent Benefits', readonly=True)

    @classmethod
    def _export_skips(cls):
        return super(Benefit, cls)._export_skips() | {'parent_benefits'}


class BenefitDependencyRelation(model.CoogSQL):
    'Benefit Dependency Relation'
    __name__ = 'benefit-benefit'

    master = fields.Many2One('benefit', 'Master', required=True, select=True,
        ondelete='CASCADE')
    slave = fields.Many2One('benefit', 'Slave', required=True, select=True,
        ondelete='RESTRICT')
