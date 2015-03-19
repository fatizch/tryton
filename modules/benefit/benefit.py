# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, coop_date, fields, coop_string
from trytond.modules.offered import offered
from trytond.modules.offered_insurance import offered as product

__metaclass__ = PoolMeta
__all__ = [
    'EventDescription',
    'LossDescriptionDocumentDescriptionRelation',
    'LossDescription',
    'EventDescriptionLossDescriptionRelation',
    'Benefit',
    'InsuranceBenefit',
    'BenefitLossDescriptionRelation',
    'OptionDescriptionBenefitRelation',
    'LossDescriptionExtraDataRelation',
    'BenefitExtraDataRelation',
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


class EventDescription(model.CoopSQL, model.CoopView):
    'Event Description'

    __name__ = 'benefit.event.description'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    loss_descs = fields.Many2Many('benefit.event.description-loss.description',
        'event_desc', 'loss_desc', 'Loss Descriptions',
        domain=[('company', '=', Eval('company'))], depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(EventDescription, cls)._export_light() |
            set(['loss_descs']))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class LossDescription(model.CoopSQL, model.CoopView):
    'Loss Description'

    __name__ = 'benefit.loss.description'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    event_descs = fields.Many2Many(
        'benefit.event.description-loss.description', 'loss_desc',
        'event_desc', 'Events Descriptions',
        domain=[('company', '=', Eval('company'))], depends=['company'])
    item_kind = fields.Selection([('', '')], 'Kind')
    item_kind_string = item_kind.translated('item_kind')
    with_end_date = fields.Boolean('With End Date')
    extra_data_def = fields.Many2Many(
        'benefit.loss.description-extra_data',
        'loss_desc', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'loss')], )
    documents = fields.Many2Many(
        'benefit.loss.description-document.description', 'loss', 'document',
        'Documents')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    def get_documents(self):
        if not (hasattr(self, 'documents') and self.documents):
            return []

        return self.documents

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None


class LossDescriptionDocumentDescriptionRelation(model.CoopSQL):
    'Loss Description to Document Description Relation'

    __name__ = 'benefit.loss.description-document.description'

    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT')
    loss = fields.Many2One('benefit.loss.description', 'Loss',
        ondelete='CASCADE')


class LossDescriptionExtraDataRelation(model.CoopSQL):
    'Relation between Loss Description and Extra Data'

    __name__ = 'benefit.loss.description-extra_data'

    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class EventDescriptionLossDescriptionRelation(model.CoopSQL):
    'Event Description - Loss Description Relation'

    __name__ = 'benefit.event.description-loss.description'

    event_desc = fields.Many2One('benefit.event.description',
        'Event Description', ondelete='CASCADE')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='RESTRICT')


class Benefit(model.CoopSQL, offered.Offered):
    'Benefit'

    __name__ = 'benefit'

    benefit_rules = fields.One2Many('benefit.rule', 'offered', 'Benefit Rules',
        delete_missing=True)
    reserve_rules = fields.One2Many('benefit.reserve.rule', 'offered',
        'Reserve Rules', delete_missing=True)
    indemnification_kind = fields.Selection(INDEMNIFICATION_KIND,
        'Indemnification Kind', sort=False, required=True)
    indemnification_kind_string = indemnification_kind.translated(
        'indemnification_kind')
    loss_descs = fields.Many2Many('benefit-loss.description', 'benefit',
        'loss_desc', 'Loss Descriptions',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        required=True)
    extra_data_def = fields.Many2Many('benefit-extra_data',
        'benefit', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'benefit')])
    use_local_currency = fields.Boolean('Use Local Currency')
    beneficiary_kind = fields.Selection('get_beneficiary_kind',
        'Beneficiary Kind', required=True, sort=False)
    beneficiary_kind_string = beneficiary_kind.translated('beneficiary_kind')

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
            # For indemnification we could have a list of result because the
            # indemnification could change over time for example 3 month at
            # 100% then 50% for the rest of the period
            coverage = args['coverage']
            try:
                # we first check that no rule are defined at a higher level
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
            # to retrieve the end date, we use the last calculated indemnificat
            indemn_dict = indemn_dicts[-1]
            if (self.indemnification_kind == 'period'
                    and 'end_date' in indemn_dict):
                sub_args['start_date'] = coop_date.add_day(
                    indemn_dict['end_date'], 1)
        return res, errs

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

    def get_extra_data_for_exec(self, args):
        all_schemas = set(self.get_extra_data_def('benefit',
            args['date']))
        return all_schemas, all_schemas

    def give_me_calculated_extra_datas(self, args):
        # We prepare the call to the 'calculate_value_set' API.
        # It needs the following parameters:
        #  - The list of the schemas it must look for
        #  - The list of all the schemas in the tree. This list should
        #    contain all the schemas from the first list
        #  - All the values available for all relevent schemas
        if 'loss' not in args or 'date' not in args:
            raise Exception('Expected loss and date in args, got %s' % (
                str([k for k in args.iterkeys()])))
        all_schemas, possible_schemas = self.get_extra_data_for_exec(args)
        existing_data = args['loss'].extra_data
        existing_data.update(args['service'].extra_data)
        ExtraData = Pool().get('extra_data')
        result = ExtraData.calculate_value_set(
            possible_schemas, all_schemas, existing_data, args)
        return result, ()

    def give_me_documents(self, args):
        try:
            res, errs = self.get_result('documents', args, kind='document')
        except offered.NonExistingRuleKindException:
            return [], []

        return res, errs


class InsuranceBenefit(product.Offered):
    'Insurance Benefit'

    __name__ = 'benefit'
    # This empty override is necessary to have in the benefit the fields added
    # in the override of offered


class BenefitLossDescriptionRelation(model.CoopSQL):
    'Benefit Loss Description Relation'

    __name__ = 'benefit-loss.description'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='RESTRICT')


class OptionDescriptionBenefitRelation(model.CoopSQL):
    'Option Description to Benefit Relation'

    __name__ = 'option.description-benefit'

    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE')
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT')


class BenefitExtraDataRelation(model.CoopSQL):
    'Benefit to Extra Data Relation'

    __name__ = 'benefit-extra_data'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
     ondelete='RESTRICT')
