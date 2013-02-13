#-*- coding:utf-8 -*-
from trytond.model import fields

from trytond.modules.coop_utils import model, utils, date
from trytond.modules.insurance_product import Offered

__all__ = [
    'EventDesc',
    'LossDescDocumentsRelation',
    'LossDesc',
    'EventDescLossDescRelation',
    'Benefit',
    'BenefitLossDescRelation',
    'CoverageBenefitRelation',
    'LossDescComplementaryDataRelation',
]

INDEMNIFICATION_KIND = [
    ('capital', 'Capital'),
    ('period', 'Period'),
]
INDEMNIFICATION_DETAIL_KIND = [
    ('waiting_period', 'Waiting Period'),
    ('deductible', 'Deductible'),
    ('benefit', 'Indemnified'),
    ('limit', 'Limit'),
]


class EventDesc(model.CoopSQL, model.CoopView):
    'Event Desc'

    __name__ = 'ins_product.event_desc'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    loss_descs = fields.Many2Many('ins_product.event_desc-loss_desc',
        'event_desc', 'loss_desc', 'Loss Descriptions')


class LossDescDocumentsRelation(model.CoopSQL):
    'Loss Desc to Document relation'

    __name__ = 'ins_product.loss-document-relation'

    document = fields.Many2One(
        'ins_product.document_desc',
        'Document',
        ondelete='RESTRICT',
    )

    loss = fields.Many2One(
        'ins_product.loss_desc',
        'Loss',
        ondelete='CASCADE',
    )


class LossDesc(model.CoopSQL, model.CoopView):
    'Loss Desc'

    __name__ = 'ins_product.loss_desc'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    event_descs = fields.Many2Many('ins_product.event_desc-loss_desc',
        'loss_desc', 'event_desc', 'Events Descriptions')
    item_kind = fields.Selection('get_possible_item_kind', 'Kind')
    with_end_date = fields.Boolean('With End Date')
    complementary_data_def = fields.Many2Many(
        'ins_product.loss_desc-complementary_data_def',
        'loss_desc', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'loss')], )
    documents = fields.Many2Many(
        'ins_product.loss-document-relation',
        'loss',
        'document',
        'Documents',
    )

    @classmethod
    def get_possible_item_kind(cls):
        return [('', '')]

    def get_documents(self):
        if not (hasattr(self, 'documents') and self.documents):
            return []

        return self.documents


class LossDescComplementaryDataRelation(model.CoopSQL):
    'Relation between Loss Desc and Complementary Data'

    __name__ = 'ins_product.loss_desc-complementary_data_def'

    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Desc',
        ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'ins_product.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')


class EventDescLossDescRelation(model.CoopSQL):
    'Event Desc - Loss Desc Relation'

    __name__ = 'ins_product.event_desc-loss_desc'

    event_desc = fields.Many2One('ins_product.event_desc', 'Event Desc',
        ondelete='CASCADE')
    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Desc',
        ondelete='RESTRICT')


class Benefit(model.CoopSQL, Offered):
    'Benefit'

    __name__ = 'ins_product.benefit'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    benefit_rules = fields.One2Many('ins_product.benefit_rule',
        'offered', 'Benefit Rules')
    reserve_rules = fields.One2Many('ins_product.reserve_rule',
        'offered', 'Reserve Rules')
    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False)
    loss_descs = fields.Many2Many('ins_product.benefit-loss_desc',
        'benefit', 'loss_desc', 'Loss Descriptions')

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Benefit, cls).delete(entities)

    @staticmethod
    def default_kind():
        return 'capital'

    def give_me_indemnification(self, args):
        res = {}
        errs = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            indemn_dict, indemn_errs = self.get_result(key, args, key)
            print key, indemn_dict, indemn_errs
            errs += indemn_errs
            if not indemn_dict:
                continue
            res[key] = indemn_dict
            if (self.indemnification_kind == 'period'
                and 'end_date' in indemn_dict):
                args['start_date'] = date.add_day(indemn_dict['end_date'], 1)
        return res, errs


class BenefitLossDescRelation(model.CoopSQL):
    'Benefit Loss Desc Relation'

    __name__ = 'ins_product.benefit-loss_desc'

    benefit = fields.Many2One('ins_product.benefit', 'Benefit',
        ondelete='CASCADE')
    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Desc',
        ondelete='RESTRICT')


class CoverageBenefitRelation(model.CoopSQL):
    'Coverage Benefit Relation'

    __name__ = 'ins_product.coverage-benefit'

    coverage = fields.Many2One('ins_product.coverage', 'Coverage',
        ondelete='CASCADE')
    benefit = fields.Many2One('ins_product.benefit', 'Benefit',
        ondelete='RESTRICT')
