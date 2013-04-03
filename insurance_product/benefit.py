#-*- coding:utf-8 -*-
from trytond.modules.coop_utils import model, date, fields
from trytond.modules.insurance_product import product
from trytond.modules.insurance_product import EligibilityResultLine

__all__ = [
    'EventDesc',
    'LossDescDocumentsRelation',
    'LossDesc',
    'EventDescLossDescRelation',
    'Benefit',
    'BenefitLossDescRelation',
    'CoverageBenefitRelation',
    'LossDescComplementaryDataRelation',
    'BenefitComplementaryDataRelation',
]

INDEMNIFICATION_KIND = [
    ('capital', 'Capital'),
    ('period', 'Period'),
    ('annuity', 'Annuity'),
]
INDEMNIFICATION_DETAIL_KIND = [
    ('waiting_period', 'Waiting Period'),
    ('deductible', 'Deductible'),
    ('benefit', 'Indemnified'),
    ('limit', 'Limit'),
]
CURRENCY_SETTING = [
    ('specific', 'Specific'),
    ('coverage', 'Coverage'),
    ('')
]


class EventDesc(model.CoopSQL, model.CoopView):
    'Event Desc'

    __name__ = 'ins_product.event_desc'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    loss_descs = fields.Many2Many(
        'ins_product.event_desc-loss_desc', 'event_desc', 'loss_desc',
        'Loss Descriptions')


class LossDescDocumentsRelation(model.CoopSQL):
    'Loss Desc to Document relation'

    __name__ = 'ins_product.loss-document-relation'

    document = fields.Many2One('ins_product.document_desc', 'Document',
        ondelete='RESTRICT')
    loss = fields.Many2One(
        'ins_product.loss_desc', 'Loss', ondelete='CASCADE')


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
    documents = fields.Many2Many('ins_product.loss-document-relation',
        'loss', 'document', 'Documents')

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


class Benefit(model.CoopSQL, product.Offered):
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
    complementary_data_def = fields.Many2Many(
        'ins_product.benefit-complementary_data_def',
        'benefit', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'benefit')])
    use_local_currency = fields.Boolean('Use Local Currency')

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Benefit, cls).delete(entities)

    @staticmethod
    def default_indemnification_kind():
        return 'capital'

    def give_me_indemnification(self, args):
        res = {}
        errs = []
        sub_args = args.copy()
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            #For indemnification we could have a list of result because the
            #indemnification could change over time for example 3 month at 100%
            #then 50% for the rest of the period
            indemn_dicts, indemn_errs = self.get_result(key, sub_args, key)
            errs += indemn_errs
            if not indemn_dicts:
                continue
            res[key] = indemn_dicts
            #to retrieve the end date, we use the last calculated indemnificat
            indemn_dict = indemn_dicts[-1]
            if (self.indemnification_kind == 'period'
                    and 'end_date' in indemn_dict):
                sub_args['start_date'] = date.add_day(
                    indemn_dict['end_date'], 1)
        return res, errs

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except product.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res


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


class BenefitComplementaryDataRelation(model.CoopSQL):
    'Relation between Benefit and Complementary Data'

    __name__ = 'ins_product.benefit-complementary_data_def'

    benefit = fields.Many2One('ins_product.benefit', 'Benefit',
        ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'ins_product.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')
