# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from sql import Null
from trytond.i18n import gettext
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond import backend
from trytond.cache import Cache

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.offered.extra_data import with_extra_data
from trytond.modules.offered.extra_data import with_extra_data_def
from trytond.modules.offered.extra_data import ExtraDataDefTable


__all__ = [
    'ClosingReason',
    'LossDescriptionClosingReason',
    'EventDescription',
    'LossDescription',
    'EventDescriptionLossDescriptionRelation',
    'Benefit',
    'BenefitLossDescriptionRelation',
    'OptionDescriptionBenefitRelation',
    'LossDescriptionExtraDataRelation',
    'BenefitExtraDataRelation',
    ]


class ClosingReason(model.CodedMixin, model.CoogView):
    'Closing Reason'

    __name__ = 'claim.closing_reason'


class LossDescriptionClosingReason(model.ConfigurationMixin):
    'Relation between Loss Description and Closing Reason'

    __name__ = 'loss.description-claim.closing_reason'

    closing_reason = fields.Many2One('claim.closing_reason', 'Closing Reason',
        required=True, ondelete='CASCADE')
    loss_description = fields.Many2One('benefit.loss.description',
        'Benefit Loss Description', required=True, ondelete='CASCADE',
        select=True)


class EventDescription(model.CodedMixin, model.CoogView):
    'Event Description'

    __name__ = 'benefit.event.description'

    loss_descs = fields.Many2Many('benefit.event.description-loss.description',
        'event_desc', 'loss_desc', 'Loss Descriptions',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    sequence = fields.Integer('Sequence')

    @classmethod
    def __register__(cls, module_name):
        super(EventDescription, cls).__register__(module_name)
        table = cls.__table__()
        # Migration from 2.6: Name is required
        cursor = Transaction().connection.cursor()
        cursor.execute(*table.update(
                columns=[table.name],
                values=[table.code],
                where=(table.name == Null)))

    @classmethod
    def __setup__(cls):
        super(EventDescription, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

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


class LossDescription(model.CodedMixin, model.CoogView, with_extra_data_def(
            'benefit.loss.description-extra_data', 'loss_desc', 'loss')):
    'Loss Description'

    __name__ = 'benefit.loss.description'

    event_descs = fields.Many2Many(
        'benefit.event.description-loss.description', 'loss_desc',
        'event_desc', 'Events Descriptions',
        order=[('event_desc.sequence', 'ASC')],
        domain=[('company', '=', Eval('company'))], depends=['company'])
    item_kind = fields.Selection([('', '')], 'Kind')
    item_kind_string = item_kind.translated('item_kind')
    has_end_date = fields.Boolean('With End Date')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    loss_kind = fields.Selection([('generic', 'Generic')], 'Loss Kind')
    closing_reasons = fields.Many2Many('loss.description-claim.closing_reason',
        'loss_description', 'closing_reason', 'Closing Reasons')
    contract_hold_sub_status = fields.Many2One('contract.sub_status',
        'Contract Hold Sub Status', ondelete='RESTRICT',
        domain=[('status', '=', 'hold')], help='If set, a claim declared with '
        'this loss will hold the contracts of the covered person with this '
        'sub status.')

    _get_loss_description_cache = Cache('get_loss_description')

    @classmethod
    def __register__(cls, module):
        table = backend.get('TableHandler')(cls, module)
        loss_desc = cls.__table__()
        # Migration from 2.0: Rename with_end_date
        if table.column_exist('with_end_date'):
            table.column_rename('with_end_date', 'has_end_date')
        # Migration from 2.6: Name is required
        super(LossDescription, cls).__register__(module)
        cursor = Transaction().connection.cursor()
        cursor.execute(*loss_desc.update(
                columns=[loss_desc.name],
                values=[loss_desc.code],
                where=(loss_desc.name == Null)))

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

    @classmethod
    def create(cls, vlist):
        created = super(LossDescription, cls).create(vlist)
        cls._get_loss_description_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(LossDescription, cls).delete(ids)
        cls._get_loss_description_cache.clear()

    @classmethod
    def write(cls, *args):
        super(LossDescription, cls).write(*args)
        cls._get_loss_description_cache.clear()

    @classmethod
    def get_loss_description(cls, code):
        loss_desc_id = cls._get_loss_description_cache.get(code, default=-1)
        if loss_desc_id != -1:
            return cls(loss_desc_id)
        instance = cls.search([('code', '=', code)])[0]
        cls._get_loss_description_cache.set(code, instance.id)
        return instance


class LossDescriptionExtraDataRelation(ExtraDataDefTable):
    'Relation between Loss Description and Extra Data'

    __name__ = 'benefit.loss.description-extra_data'

    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')


class EventDescriptionLossDescriptionRelation(model.ConfigurationMixin):
    'Event Description - Loss Description Relation'

    __name__ = 'benefit.event.description-loss.description'

    event_desc = fields.Many2One('benefit.event.description',
        'Event Description', ondelete='CASCADE')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='RESTRICT')


class Benefit(model.CodedMixin, model.CoogView,
        with_extra_data_def('benefit-extra_data', 'benefit', 'benefit'),
        with_extra_data(['product'], field_string='Offered Kind'),
        model.TaggedMixin):
    'Benefit'

    __name__ = 'benefit'

    logger = logging.getLogger(__name__)

    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    description = fields.Text('Description', translate=True)
    loss_descs = fields.Many2Many('benefit-loss.description', 'benefit',
        'loss_desc', 'Loss Descriptions',
        help='Loss description list when the benefit can be delivered',
        domain=[('company', '=', Eval('company'))], depends=['company'],
        required=True)
    beneficiary_kind = fields.Selection('get_beneficiary_kind',
        'Beneficiary Kind', help='Define who will benefit of the benefit',
        required=True, sort=False)
    beneficiary_kind_string = beneficiary_kind.translated('beneficiary_kind')
    automatically_deliver = fields.Boolean('Automatically Deliver',
        help='If True the benefit will automatically be delivered after loss '
        'declaration')
    insurer = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        required=True, select=True)
    options = fields.Many2Many('option.description-benefit', 'benefit',
        'coverage', 'Options', readonly=True)
    several_delivered = fields.Boolean('Several delivered',
        help='If true, it will be possible to deliver the same benefit '
        'several times')
    may_have_origin = fields.Boolean('May Have an Origin',
        help='If True, services based on this benefit will have the '
        'possibility to select an "origin service", which represents the '
        'service that preceded it')
    show_benefit = fields.Function(
        fields.Boolean('Show Benefit', depends=['beneficiary_kind']),
        'on_change_with_show_benefit')

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls.extra_data.help = 'Extra data to characterize the benefit. These '\
            'extra data are available in rule engine.'
        cls.extra_data_def.help = 'List of extra data that will be requested '\
            'for delivering this benefit in a claim. These data can be used '\
            'in rule engine and will be versioned and store on the delivered '\
            'service'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        insurer_exist = table.column_exist('insurer')
        super(Benefit, cls).__register__(module_name)

        # Migration from 1.6 Drop Offered inheritance
        if table.column_exist('template'):
            table.drop_column('template')
            table.drop_column('template_behaviour')

        # Migration from 1.12: Insurer is now required on benefits
        if not insurer_exist:
            cls._migrate_insurer_benefit()

    @classmethod
    def _export_light(cls):
        return super(Benefit, cls)._export_light() | {'company', 'loss_descs'}

    @classmethod
    def _export_skips(cls):
        return super(Benefit, cls)._export_skips() | {'options'}

    @classmethod
    def _migrate_insurer_benefit(cls):
        benefits = cls.search([])
        to_write = []
        for benefit in benefits:
            insurers = list({x.insurer for x in benefit.options})
            if len(insurers) != 1:
                cls.logger.warning('Impossible to migrate insurer for the '
                    'benefit %s (%s possible insurer(s) found)' % (
                        benefit.rec_name, len(insurers)))
            else:
                to_write += [[benefit], {'insurer': insurers[0].id}]
        if to_write:
            cls.write(*to_write)

    @classmethod
    def copy(cls, instances, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('options', None)
        return super(Benefit, cls).copy(instances, default=default)

    @fields.depends('beneficiary_kind')
    def on_change_with_show_benefit(self, name=None):
        return self.beneficiary_kind != 'subscriber'

    @classmethod
    def get_beneficiary_kind(cls):
        return [
            ('subscriber', gettext('claim.msg_subscriber_enum')),
            ('other', gettext('claim.msg_other_enum')),
            ]

    @staticmethod
    def default_beneficiary_kind():
        return 'subscriber'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @classmethod
    def view_attributes(cls):
        return super(Benefit, cls).view_attributes() + [
            ('/form/notebook/page[@id="managers"]/notebook/'
                'page[@id="beneficiary"]',
                'states',
                {'invisible': ~Eval('show_benefit')})
            ]

    def init_dict_for_rule_engine(self, args):
        args['benefit'] = self

    @classmethod
    def is_master_object(cls):
        return True

    def get_documentation_structure(self):
        structure = {
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'parameters': [
                coog_string.doc_for_field(self, 'company'),
                coog_string.doc_for_field(self, 'start_date'),
                coog_string.doc_for_field(self, 'end_date'),
                coog_string.doc_for_field(self, 'insurer'),
                coog_string.doc_for_field(self, 'beneficiary_kind'),
                coog_string.doc_for_field(self, 'extra_data'),
                coog_string.doc_for_field(self, 'extra_data_def'),
                coog_string.doc_for_field(self, 'tags'),
                coog_string.doc_for_field(self, 'automatically_deliver'),
                coog_string.doc_for_field(self, 'several_delivered'),
                coog_string.doc_for_field(self, 'may_have_origin'),
                ],
            'rules': [
                ],
            }
        return structure


class BenefitLossDescriptionRelation(model.ConfigurationMixin):
    'Benefit Loss Description Relation'

    __name__ = 'benefit-loss.description'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='RESTRICT')


class OptionDescriptionBenefitRelation(model.ConfigurationMixin):
    'Option Description to Benefit Relation'

    __name__ = 'option.description-benefit'

    coverage = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE')
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT')


class BenefitExtraDataRelation(ExtraDataDefTable):
    'Benefit to Extra Data Relation'

    __name__ = 'benefit-extra_data'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
     ondelete='RESTRICT')
