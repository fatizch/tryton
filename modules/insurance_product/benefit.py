#-*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, coop_date, fields
from trytond.modules.offered import offered
from trytond.modules.offered import EligibilityResultLine
from .product import Offered

__all__ = [
    'EventDesc',
    'LossDescDocumentsRelation',
    'LossDesc',
    'EventDescLossDescRelation',
    'Benefit',
    'InsuranceBenefit',
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
    ('regularization', 'Regularization'),
]
CURRENCY_SETTING = [
    ('specific', 'Specific'),
    ('coverage', 'Coverage'),
    ('')
]


class EventDesc(model.CoopSQL, model.CoopView):
    'Event Desc'

    __name__ = 'benefit.event.description'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    loss_descs = fields.Many2Many(
        'benefit.event.description-loss.description', 'event_desc', 'loss_desc',
        'Loss Descriptions', domain=[('company', '=', Eval('company'))],
        depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    def __export_json(self, skip_fields=None):
        if skip_fields is None:
            skip_fields = set()
        skip_fields.add('loss_descs')
        return super(EventDesc, self).export_json(skip_fields)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None


class LossDescDocumentsRelation(model.CoopSQL):
    'Loss Desc to Document relation'

    __name__ = 'ins_product.loss-document-relation'

    document = fields.Many2One(
        'ins_product.document_desc', 'Document', ondelete='RESTRICT')
    loss = fields.Many2One(
        'benefit.loss.description', 'Loss', ondelete='CASCADE')


class LossDesc(model.CoopSQL, model.CoopView):
    'Loss Desc'

    __name__ = 'benefit.loss.description'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    event_descs = fields.Many2Many(
        'benefit.event.description-loss.description', 'loss_desc', 'event_desc',
        'Events Descriptions', domain=[('company', '=', Eval('company'))],
        depends=['company'])
    item_kind = fields.Selection('get_possible_item_kind', 'Kind')
    with_end_date = fields.Boolean('With End Date')
    complementary_data_def = fields.Many2Many(
        'benefit.loss.description-extra_data',
        'loss_desc', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'loss')], )
    documents = fields.Many2Many(
        'ins_product.loss-document-relation', 'loss', 'document', 'Documents')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    @classmethod
    def get_possible_item_kind(cls):
        return [('', '')]

    def get_documents(self):
        if not (hasattr(self, 'documents') and self.documents):
            return []

        return self.documents

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None


class LossDescComplementaryDataRelation(model.CoopSQL):
    'Relation between Loss Desc and Complementary Data'

    __name__ = 'benefit.loss.description-extra_data'

    loss_desc = fields.Many2One(
        'benefit.loss.description', 'Loss Desc', ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'offered.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')


class EventDescLossDescRelation(model.CoopSQL):
    'Event Desc - Loss Desc Relation'

    __name__ = 'benefit.event.description-loss.description'

    event_desc = fields.Many2One(
        'benefit.event.description', 'Event Desc', ondelete='CASCADE')
    loss_desc = fields.Many2One(
        'benefit.loss.description', 'Loss Desc', ondelete='RESTRICT')


class Benefit(model.CoopSQL, offered.Offered):
    'Benefit'

    __name__ = 'benefit'

    benefit_rules = fields.One2Many(
        'ins_product.benefit_rule', 'offered', 'Benefit Rules')
    reserve_rules = fields.One2Many(
        'ins_product.reserve_rule', 'offered', 'Reserve Rules')
    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False, required=True)
    loss_descs = fields.Many2Many(
        'benefit-loss.description', 'benefit', 'loss_desc',
        'Loss Descriptions', domain=[('company', '=', Eval('company'))],
        depends=['company'], required=True)
    complementary_data_def = fields.Many2Many(
        'benefit-extra_data',
        'benefit', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', '=', 'benefit')])
    use_local_currency = fields.Boolean('Use Local Currency')
    beneficiary_kind = fields.Selection('get_beneficiary_kind',
        'Beneficiary Kind', required=True, sort=False)

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

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
            coverage = args['coverage']
            try:
                #we first check that no rule are defined at a higher level
                indemn_dicts, indemn_errs = coverage.get_result(key, sub_args,
                    key)
            except offered.NonExistingRuleKindException:
                try:
                    indemn_dicts, indemn_errs = self.get_result(key,
                        sub_args, key)
                except offered.NonExistingRuleKindException:
                    continue
            errs += indemn_errs
            if not indemn_dicts:
                continue
            res[key] = indemn_dicts
            #to retrieve the end date, we use the last calculated indemnificat
            indemn_dict = indemn_dicts[-1]
            if (self.indemnification_kind == 'period'
                    and 'end_date' in indemn_dict):
                sub_args['start_date'] = coop_date.add_day(
                    indemn_dict['end_date'], 1)
        return res, errs

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, kind='eligibility')
        except offered.NonExistingRuleKindException:
            return (EligibilityResultLine(True), [])
        return res

    @classmethod
    def get_beneficiary_kind(cls):
        return [
                ('subscriber', 'Subscriber'),
                ('other', 'Other'),
            ]

    @staticmethod
    def default_beneficiary_kind():
        return 'subscriber'

    def init_dict_for_rule_engine(self, args):
        super(Benefit, self).init_dict_for_rule_engine(args)
        args['benefit'] = self

    def get_compl_data_for_exec(self, args):
        all_schemas = set(self.get_complementary_data_def('benefit',
            args['date']))
        return all_schemas, all_schemas

    def give_me_calculated_complementary_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if not 'loss' in args or not 'date' in args:
            raise Exception('Expected loss and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = self.get_compl_data_for_exec(args)
        existing_data = args['loss'].complementary_data
        existing_data.update(args['delivered_service'].complementary_data)
        ComplementaryData = Pool().get('offered.complementary_data_def')
        result = ComplementaryData.calculate_value_set(
            possible_schemas, all_schemas, existing_data, args)
        return result, ()


class InsuranceBenefit(Offered):
    'Insurance Benefit'

    __name__ = 'benefit'
    #This empty override is necessary to have in the benefit the fields added
    #in the override of offered


class BenefitLossDescRelation(model.CoopSQL):
    'Benefit Loss Desc Relation'

    __name__ = 'benefit-loss.description'

    benefit = fields.Many2One(
        'benefit', 'Benefit', ondelete='CASCADE')
    loss_desc = fields.Many2One(
        'benefit.loss.description', 'Loss Desc', ondelete='RESTRICT')


class CoverageBenefitRelation(model.CoopSQL):
    'Coverage Benefit Relation'

    __name__ = 'offered.coverage-benefit'

    coverage = fields.Many2One(
        'offered.coverage', 'Coverage', ondelete='CASCADE')
    benefit = fields.Many2One(
        'benefit', 'Benefit', ondelete='RESTRICT')


class BenefitComplementaryDataRelation(model.CoopSQL):
    'Relation between Benefit and Complementary Data'

    __name__ = 'benefit-extra_data'

    benefit = fields.Many2One(
        'benefit', 'Benefit', ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'offered.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')
