# -*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond import backend

from trytond.modules.cog_utils import model, fields, coop_string, utils

__metaclass__ = PoolMeta
__all__ = [
    'EventDescription',
    'LossDescription',
    'EventDescriptionLossDescriptionRelation',
    'Benefit',
    'BenefitLossDescriptionRelation',
    'OptionDescriptionBenefitRelation',
    'LossDescriptionExtraDataRelation',
    'BenefitExtraDataRelation',
    ]


class EventDescription(model.CoopSQL, model.CoopView):
    'Event Description'

    __name__ = 'benefit.event.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    loss_descs = fields.Many2Many('benefit.event.description-loss.description',
        'event_desc', 'loss_desc', 'Loss Descriptions',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(EventDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]

    @classmethod
    def _export_light(cls):
        return super(EventDescription, cls)._export_light() | {'company'}

    @classmethod
    def _export_skips(cls):
        return super(EventDescription, cls)._export_skips() | {'loss_descs'}

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class LossDescription(model.CoopSQL, model.CoopView):
    'Loss Description'

    __name__ = 'benefit.loss.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    event_descs = fields.Many2Many(
        'benefit.event.description-loss.description', 'loss_desc',
        'event_desc', 'Events Descriptions',
        domain=[('company', '=', Eval('company'))], depends=['company'])
    item_kind = fields.Selection([('', '')], 'Kind')
    item_kind_string = item_kind.translated('item_kind')
    extra_data_def = fields.Many2Many(
        'benefit.loss.description-extra_data',
        'loss_desc', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'loss')], )
    with_end_date = fields.Boolean('With End Date')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    loss_kind = fields.Selection([('generic', 'Generic')], 'Loss Kind')

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return super(LossDescription, cls)._export_light() | {'company',
            'event_descs'}

    @classmethod
    def default_loss_kind(cls):
        return 'generic'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None


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


class Benefit(model.CoopSQL, model.CoopView, model.TaggedMixin):
    'Benefit'

    __name__ = 'benefit'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    extra_data = fields.Dict('extra_data', 'Offered Kind',
        context={'extra_data_kind': 'product'},
        domain=[('kind', '=', 'product')])
    extra_data_string = extra_data.translated('extra_data')
    loss_descs = fields.Many2Many('benefit-loss.description', 'benefit',
        'loss_desc', 'Loss Descriptions',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        required=True)
    extra_data_def = fields.Many2Many('benefit-extra_data',
        'benefit', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'benefit')])
    beneficiary_kind = fields.Selection('get_beneficiary_kind',
        'Beneficiary Kind', required=True, sort=False)
    beneficiary_kind_string = beneficiary_kind.translated('beneficiary_kind')

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Benefit, cls).__register__(module_name)

        # Migration from 1.6 Drop Offered inheritance
        if table.column_exist('template'):
            table.drop_column('template')
            table.drop_column('template_behaviour')

    @classmethod
    def delete(cls, entities):
        cls.delete_rules(entities)
        super(Benefit, cls).delete(entities)

    @classmethod
    def _export_light(cls):
        return super(Benefit, cls)._export_light() | {'company'}

    @classmethod
    def get_beneficiary_kind(cls):
        return [
            ('subscriber', 'Subscriber'),
            ('other', 'Other'),
            ]

    @staticmethod
    def default_beneficiary_kind():
        return 'subscriber'

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date', None) or utils.today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    def init_dict_for_rule_engine(self, args):
        args['benefit'] = self

    def get_extra_data_for_exec(self, args):
        all_schemas = set(self.get_extra_data_def('benefit',
            args['date']))
        return all_schemas, all_schemas

    def get_extra_data_def(self, existing_data, condition_date):
        ExtraData = Pool().get('extra_data')
        all_schemas, possible_schemas = ExtraData.get_extra_data_definitions(
            self, 'extra_data_def', 'benefit', condition_date)
        return ExtraData.calculate_value_set(possible_schemas, all_schemas,
            existing_data)

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return self.code if self.code else coop_string.slugify(self.name)


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
