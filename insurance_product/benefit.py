#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model, utils
from trytond.modules.insurance_product import Offered

__all__ = [
    'Benefit'
    ]


class Benefit(model.CoopSQL, Offered):
    'Benefit'

    __name__ = 'ins_product.benefit'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    benefit_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Benefit Manager')
    reserve_mgr = model.One2ManyDomain('ins_product.business_rule_manager',
        'offered', 'Reserve Manager')
    kind = fields.Selection(
        [
            ('capital', 'Capital'),
            ('per_diem', 'Per Diem'),
            ('annuity', 'Annuity')
        ],
        'Kind', required=True)

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        super(Benefit, cls).delete(entities)

    @staticmethod
    def default_kind():
        return 'capital'
