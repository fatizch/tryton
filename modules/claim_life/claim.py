# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from sql.aggregate import Min

from sql import Literal
from sql.aggregate import Max
from sql.conditionals import Coalesce

from trytond import backend

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool, And
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.report_engine import Printable
from trytond.modules.offered.extra_data import with_extra_data
from trytond.modules.claim.claim import CLAIM_READONLY

from datetime import timedelta

__all__ = [
    'Claim',
    'ClaimBeneficiary',
    'Loss',
    'ClaimService',
    'Indemnification',
    'DocumentRequestLine',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    beneficiaries = fields.Function(
        fields.Many2Many('claim.beneficiary', None, None, 'Beneficiaries',
            help='The beneficiaries for the different services for which '
            'they must be set manually',
            domain=[('service', 'in', Eval('services_with_beneficiaries'))],
            context={'field_services':
                Eval('services_with_beneficiaries', [])},
            states={'invisible': ~Eval('services_with_beneficiaries')},
            depends=['services_with_beneficiaries']),
        'getter_beneficiaries', 'setter_void')
    services_with_beneficiaries = fields.Function(
        fields.Many2Many('claim.service', None, None,
            'Services with beneficiaries'),
        'getter_services_with_beneficiaries')

    def getter_beneficiaries(self, name):
        return [beneficiary.id for loss in self.losses
            for service in loss.services
            for beneficiary in service.beneficiaries]

    def getter_services_with_beneficiaries(self, name):
        return [service.id for loss in self.losses
            for service in loss.services
            if service.benefit.beneficiary_kind == 'manual_list']

    def add_new_relapse(self, loss_desc_code):
        event_desc = None
        for loss in self.losses:
            if loss.loss_desc.loss_kind == 'std':
                event_desc = loss.event_desc
        self.add_new_loss(loss_desc_code, is_a_relapse=True,
            event_desc=event_desc.id if event_desc else None)

    def add_new_long_term_disability(self, loss_desc_code):
        self.add_new_loss(loss_desc_code)
        assert self.losses[-1].loss_desc.code == loss_desc_code
        # Look for first short term loss and init the start date
        for loss in self.losses[:-1]:
            if loss.loss_desc.loss_kind == 'std':
                self.losses[-1].initial_std_start_date = loss.start_date
                break


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    possible_covered_persons = fields.Function(
        fields.One2Many('party.party', None, 'Covered Persons',
            states={'invisible': True}),
        'on_change_with_possible_covered_persons')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        # TODO: Temporary hack, the function field is not calculated
        # when storing the object
        states={'readonly': CLAIM_READONLY},
        domain=[If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
                )
            ],
        depends=['possible_covered_persons', 'claim_status'],
        ondelete='RESTRICT', select=True)
    start_date_string = fields.Function(
        fields.Char('Start Date String',
            depends=['loss_desc_kind', 'loss_desc']),
        'on_change_with_start_date_string')
    end_date_string = fields.Function(fields.Char('End Date String',
        states={'invisible': Bool(~Eval('with_end_date'))},
        depends=['loss_desc_kind', 'loss_desc', 'with_end_date']),
        'on_change_with_end_date_string')
    initial_std_start_date = fields.Date('Initial STD Start Date',
        states={'invisible': Eval('loss_desc_kind') != 'ltd',
            'readonly': Eval('state') != 'draft',
            'required': And(Eval('state') != 'draft',
                Eval('loss_desc_kind') == 'ltd')},
        depends=['loss_desc_kind', 'loss_desc', 'state'])
    return_to_work_date = fields.Date('Return to Work',
        states={'invisible': Eval('loss_desc_kind') != 'std'},
        domain=[If(Bool(Eval('return_to_work_date')),
                ('return_to_work_date', '>', Eval('end_date')),
                ())
            ], depends=['end_date'])
    is_a_relapse = fields.Boolean('Is A Relapse',
        states={
            'invisible': ~Eval('with_end_date'),
            'readonly': CLAIM_READONLY, },
        depends=['with_end_date', 'claim_status'])
    loss_kind = fields.Function(
        fields.Char('Loss Kind'),
        'get_loss_kind')
    relapse_initial_loss = fields.Many2One('claim.loss', 'Relapse Initial Loss',
        ondelete='RESTRICT', domain=[
            ('id', 'in', Eval('possible_relapse_losses'))],
        states={'invisible': ~Bool(Eval('is_a_relapse')),
            'required': And(Bool(Eval('is_a_relapse')),
                Eval('state') == 'active')},
        depends=['is_a_relapse', 'possible_relapse_losses', 'state'])
    possible_relapse_losses = fields.Function(
        fields.Many2Many('claim.loss', None, None, 'Possible Relapse Losses'),
        'on_change_with_possible_relapse_losses')

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)
        # Migrate from 1.12: add relapse loss for already existing relapses
        # and set it to the claim's first loss in order to keep previous
        # behaviour
        cursor = Transaction().connection.cursor()
        do_migrate = not handler.column_exist('relapse_initial_loss')
        super(Loss, cls).__register__(module)
        if not do_migrate:
            return
        loss = cls.__table__()
        loss2 = cls.__table__()

        query = loss.update(columns=[loss.relapse_initial_loss],
            values=loss2.select(Min(loss2.id),
                where=(loss2.claim == loss.claim)
                & (loss2.is_a_relapse == Literal(False))
                & (loss2.start_date < loss.start_date)
                & (loss2.loss_desc == loss.loss_desc)),
            where=(loss.is_a_relapse == Literal(True)))
        cursor.execute(*query)

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls.start_date.depends.append('loss_desc_kind')
        cls.end_date.depends.append('loss_desc_kind')
        cls._error_messages.update({
                'relapse': 'Relapse',
                'previous_loss_end_date_missing': "The previous std "
                "doesn't have an end date defined",
                'one_day_between_relapse_and_previous_loss': 'One day is '
                'required between the relapse and the previous std',
                'loss_date': 'Loss Date:',
                'start_date': 'Start Date:',
                'std_start_date': 'STD Start Date:',
                'ltd_start_date': 'LTD Start Date:',
                'end_date': 'End Date:',
                'std_end_date': 'STD End Date:',
                'ltd_end_date': 'LTD End Date:',
                'missing_relapse_initial_loss': 'The initial loss is missing on'
                ' the relapse: %(loss)s'
                })
        cls.closing_reason.states.update({
                'required': Bool(Eval('end_date')),
                })
        cls.closing_reason.depends.extend(['loss_kind', 'end_date'])

    @classmethod
    def __post_setup__(cls):
        super(Loss, cls).__post_setup__()
        Pool().get('extra_data')._register_extra_data_provider(cls,
            'find_extra_data_value', ['covered_element'])

    @fields.depends('loss_desc', 'loss_desc_kind')
    def on_change_with_start_date_string(self, name=None):
        if self.loss_desc and self.loss_desc.with_end_date:
            return self.date_string('start_date_string')
        else:
            return self.date_string('loss_date_string')

    @fields.depends('loss_desc', 'loss_desc_kind')
    def on_change_with_end_date_string(self, name=None):
        return self.date_string('end_date_string')

    def date_string(self, name=None):
        if not name:
            return ''
        key = (self.loss_desc_kind + '_') \
            if self.loss_desc_kind and self.loss_desc_kind in ('std', 'ltd') \
                and self.loss_desc and self.loss_desc.with_end_date else ''
        key += name[:-7]
        return self.raise_user_error(key, raise_exception=False)

    @fields.depends('loss_kind')
    def on_change_with_possible_loss_descs(self, name=None):
        return super(Loss, self).on_change_with_possible_loss_descs(name)

    def get_loss_kind(self, name):
        if self.loss_desc:
            return self.loss_desc.loss_kind

    def close(self, sub_status, date=None):
        super(Loss, self).close(sub_status, date)
        if date:
            self.return_to_work_date = date
            self.save()

    def get_rec_name(self, name):
        res = super(Loss, self).get_rec_name(name)
        if self.covered_person:
            res += ' - ' + self.covered_person.full_name
        if self.is_a_relapse:
            res = '%s (%s)' % (res, self.raise_user_error('relapse',
                raise_exception=False))
        return res

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('contract.covered_element')
        if not self.claim or not self.start_date:
            return []
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_parties(self.start_date))
        return res

    @fields.depends('end_date', 'available_closing_reasons')
    def on_change_with_closing_reason(self, name=None):
        super(Loss, self).on_change_with_closing_reason(name)
        if (self.end_date and
                len(self.available_closing_reasons) == 1):
            return self.available_closing_reasons[0].id
        if not self.end_date:
            return None

    @fields.depends('claim', 'start_date')
    def on_change_with_possible_covered_persons(self, name=None):
        if not self.start_date:
            return []
        return [x.id for x in self.get_possible_covered_persons()]

    @fields.depends('covered_person', 'possible_loss_descs', 'claim',
        'start_date', 'loss_desc', 'event_desc')
    def on_change_covered_person(self):
        self.possible_loss_descs = self.on_change_with_possible_loss_descs()

    @fields.depends('return_to_work_date', 'end_date')
    def on_change_return_to_work_date(self):
        self.update_end_date()

    def update_end_date(self):
        if self.return_to_work_date and not self.end_date:
            self.end_date = self.return_to_work_date - timedelta(days=1)

    @classmethod
    def add_func_key(cls, values):
        # Update without func_key is not handled for now
        values['_func_key'] = None

    def init_loss(self, loss_desc_code=None, **kwargs):
        self.return_to_work_date = None
        self.end_date = None
        self.is_a_relapse = False
        super(Loss, self).init_loss(loss_desc_code, **kwargs)
        self.covered_person = self.claim.claimant \
            if self.claim.claimant.is_person else None
        self.update_end_date()

    @property
    def date(self):
        return self.start_date

    def get_covered_person(self):
        return getattr(self, 'covered_person', None)

    def find_covered_person_extra_data_value(self, name, **kwargs):
        CoveredElement = Pool().get('contract.covered_element')
        if not self.claim:
            raise KeyError
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.covered_person, self.start_date):
            if (covered_element.party and
                    covered_element.party == self.covered_person and
                    covered_element.main_contract == self.claim.main_contract):
                return covered_element.find_extra_data_value(name, **kwargs)

    def covered_options(self):
        Option = Pool().get('contract.option')
        person = self.get_covered_person()
        if person:
            return Option.get_covered_options_from_party(person,
                self.get_date() or self.claim.declaration_date)
        return super(Loss, self).covered_options()

    def check_activation(self):
        super(Loss, self).check_activation()
        if not self.is_a_relapse:
            return
        if not self.start_date:
            return
        previous_loss = self.relapse_initial_loss
        if not previous_loss:
            self.append_functional_error('missing_relapse_initial_loss',
                {'loss': self.rec_name})
        if not previous_loss.end_date:
            self.append_functional_error('previous_loss_end_date_missing')
        if (self.start_date - previous_loss.end_date).days <= 1:
            # As it's a relapse there must be one day of work between two std
            self.append_functional_error(
                'one_day_between_relapse_and_previous_loss')

    @classmethod
    def get_possible_duplicates_fields(cls):
        return super(Loss, cls).get_possible_duplicates_fields() | {
            'covered_person',
            }

    def get_possible_duplicates_clauses(self):
        return super(Loss, self).get_possible_duplicates_clauses() + [
            ('covered_person', '=', self.covered_person.id),
            ]

    @classmethod
    def do_check_duplicates(cls):
        return True

    def get_date(self):
        if self.loss_kind == ('std', 'ltd', 'death'):
            # The initial event must be used to know if the person is covered
            if hasattr(self, 'claim') and self.claim.losses:
                return self.claim.losses[0].start_date
        return super(Loss, self).get_date()

    def total_share_valid(self, service):
        valid, total_share = super(Loss, self).total_share_valid(service)
        return service.benefit.ignore_shares or valid, total_share

    @fields.depends('covered_person', 'loss_desc', 'start_date')
    def on_change_with_possible_relapse_losses(self, name=None):
        if not self.covered_person:
            return []
        Loss = Pool().get('claim.loss')
        domain = [('covered_person', '=', self.covered_person),
                ('loss_desc', '=', self.loss_desc)]
        if self.start_date:
            domain.extend([('start_date', '!=', None),
                    ('start_date', '<', self.start_date)])
        possible_relapse_losses = Loss.search(domain)
        return [l.id for l in possible_relapse_losses if l.id != self.id]


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    beneficiaries = fields.One2Many('claim.beneficiary', 'service',
        'Beneficiaries', states={'invisible': ~Eval('manual_beneficiaries'),
            'readonly': ~Eval('manual_beneficiaries')}, delete_missing=True,
        depends=['manual_beneficiaries'])
    manual_beneficiaries = fields.Function(
        fields.Boolean('Has Beneficiaries'),
        'get_manual_beneficiaries')

    def get_covered_person(self):
        return self.loss.get_covered_person()

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(
            cur_dict)
        if self.loss.loss_desc.loss_kind == 'life':
            cur_dict['covered_person'] = self.get_covered_person()

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if not loss.is_a_relapse:
            return
        values = self.extra_datas[-1].extra_data_values
        old_values = self.loss.relapse_initial_loss.claim. \
            delivered_services[0].extra_datas[-1].extra_data_values
        for key, value in old_values.iteritems():
            if key in values:
                values[key] = value
        self.extra_datas[-1].extra_data_values = values

    def get_theoretical_covered_element(self, name):
        if self.option and self.option.covered_element:
            person = self.get_covered_person()
            if person and self.option.covered_element.party == person:
                return self.option.covered_element.id
        return super(ClaimService, self).get_theoretical_covered_element(name)

    def init_from_option(self, option):
        super(ClaimService, self).init_from_option(option)
        self.beneficiaries = self.init_beneficiaries()

    def init_beneficiaries(self):
        if self.option and getattr(self.option, 'beneficiaries', None):
            return [Pool().get('claim.beneficiary')(party=x.party,
                share=x.share) for x in self.option.beneficiaries if x.party]
        return []

    def get_manual_beneficiaries(self, name):
        return self.benefit.beneficiary_kind == 'manual_list'

    def get_beneficiaries_data(self, at_date):
        if self.benefit.beneficiary_kind == 'manual_list':
            if self.benefit.manual_share_management:
                return [(x.party, 1) for x in self.beneficiaries
                    if x.identified]
            else:
                return [(x.party, x.share) for x in self.beneficiaries
                    if x.identified]
        elif (self.benefit.beneficiary_kind == 'covered_party' and
                self.loss.covered_person):
            return [(self.loss.covered_person, 1)]
        return super(ClaimService, self).get_beneficiaries_data(at_date)

    def get_beneficiary_definition_from_party(self, party):
        if not self.manual_beneficiaries:
            return None
        for beneficiary in self.beneficiaries:
            if beneficiary.party == party:
                return beneficiary


class ClaimBeneficiary(model.CoogSQL, model.CoogView,
        with_extra_data(['beneficiary'], field_name='extra_data_values'),
        Printable):
    'Claim Beneficiary'

    __name__ = 'claim.beneficiary'

    service = fields.Many2One('claim.service', 'Service', ondelete='CASCADE',
        required=True, select=True, states={'readonly': ~Eval('id')},
        depends=['id'], domain=[('can_be_indemnified', '=', True)])
    identified = fields.Boolean('Identified Party',
        help='The beneficiary has properly been identified')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        help='The identified party that will receive part of (or all of) the '
        'calculated indemnification',
        states={'required': Bool(Eval('identified', False)),
            'readonly': Bool(Eval('identified', False))},
        depends=['identified'])
    share = fields.Numeric('Share', domain=['OR', [('share', '=', None)],
            [('share', '>', 0), ('share', '<=', 1)]],
        help='The percentage of the calculated indemnification that will be '
        'paid to this beneficiary',
        states={
            'readonly': Bool(Eval('identified', False)),
            'invisible': Bool(Eval('ignore_share', False)),
            },
        depends=['identified'])
    description = fields.Text('Description',
        help='In case the party is not properly identified, this field should '
        'be used to write down identifying informations',
        states={'required': ~Eval('party'),
            'invisible': Bool(Eval('identified', False))},
        depends=['identified', 'party'])
    document_request_lines = fields.One2Many('document.request.line',
        'for_object', 'Documents', delete_missing=True,
        help='The list of documents that will be required from the '
        'beneficiary before indemnifications can be made',
        states={'invisible': ~Eval('identified')}, depends=['identified'])
    documents_reception_date = fields.Function(
        fields.Date('Documents Reception Date',
            help='Reception date of the last document, empty if all documents '
            'are not received yet',
            states={'invisible': ~Eval('identified')}, depends=['identified']),
        'getter_documents_reception_date')
    ignore_share = fields.Function(fields.Boolean('Ignore Share'),
        'on_change_with_ignore_share')

    @classmethod
    def __setup__(cls):
        super(ClaimBeneficiary, cls).__setup__()
        cls._buttons.update({
                'identify': {
                    'readonly': ~Eval('party'),
                    'invisible': Bool(Eval('identified', False)),
                    },
                'generic_send_letter': {
                    'readonly': ~Eval('identified'),
                    'invisible': Bool(Eval('documents_reception_date')),
                    },
                })

    @classmethod
    def default_service(cls):
        ctx_services = Transaction().context.get('field_services', [])
        if ctx_services:
            services = Pool().get('claim.service').browse(ctx_services)
            possible_services = [x for x in services if x.can_be_indemnified]
            if len(possible_services) == 1:
                return possible_services[0].id

    @classmethod
    def delete(cls, beneficiaries):
        if beneficiaries:
            RequestLine = Pool().get('document.request.line')
            to_delete = RequestLine.search([
                    ('for_object', 'in', [str(x) for x in beneficiaries])])
            if to_delete:
                RequestLine.delete(to_delete)
        super(ClaimBeneficiary, cls).delete(beneficiaries)

    @fields.depends('document_request_lines')
    def on_change_with_documents_reception_date(self):
        res = None
        for document in self.document_request_lines:
            if not document.blocking:
                continue
            if not document.reception_date:
                return None
            res = max(res or datetime.date.min, document.reception_date)
        return res

    @fields.depends('document_request_lines')
    def on_change_document_request_lines(self):
        self.documents_reception_date = \
            self.on_change_with_documents_reception_date()

    @classmethod
    def getter_documents_reception_date(cls, beneficiaries, name):
        # TODO: can be improve by using only one database query
        cursor = Transaction().connection.cursor()
        dates = {x.id: None for x in beneficiaries}
        request_line = Pool().get('document.request.line').__table__()
        claims = [b.service.claim for b in beneficiaries]
        cursor.execute(*request_line.select(request_line.for_object,
                Max(Coalesce(request_line.reception_date, datetime.date.max)),
                where=(request_line.blocking == Literal(True))
                & request_line.for_object.in_(
                    [str(x) for x in claims]),
                group_by=[request_line.for_object]))
        claim_documents = {}
        for claim, date in cursor.fetchall():
            claim_documents[int(claim.split(',')[1])] = date
        cursor.execute(*request_line.select(request_line.for_object,
                Max(Coalesce(request_line.reception_date, datetime.date.max)),
                where=(request_line.blocking == Literal(True))
                & request_line.for_object.in_(
                    [str(x) for x in beneficiaries]),
                group_by=[request_line.for_object]))
        for beneficiary, date in cursor.fetchall():
            beneficiary_id = int(beneficiary.split(',')[1])
            claim_document_date = datetime.date.max
            claim_document_date = claim_documents[
                cls(beneficiary_id).service.claim.id]
            if (date == datetime.date.max or
                    claim_document_date == datetime.date.max):
                date = None
            dates[beneficiary_id] = max(date, claim_document_date)\
                if date else None
        return dates

    @model.CoogView.button_change('document_request_lines', 'identified',
        'party', 'service')
    def identify(self):
        assert self.party
        self.identified = True
        self.update_documents()

    @fields.depends('service')
    def on_change_with_ignore_share(self, name=None):
        if self.service:
            return self.service.benefit.ignore_shares

    def update_documents(self):
        DocumentRequestLine = Pool().get('document.request.line')
        documents = []
        for descriptor in self.service.benefit.beneficiary_documents:
            documents.append(DocumentRequestLine(
                    document_desc=descriptor,
                    for_object=self,
                    claim=self.service.claim,
                    blocking=True,
                    ))
        self.document_request_lines = documents

    def get_rec_name(self, name):
        if self.party:
            name = self.party.rec_name
        else:
            if len(self.description) > 50:
                name = self.description[:50] + '...'
            else:
                name = self.description
        identified = ''
        if self.identified:
            identified = '[%s] ' % coog_string.translate_field(self,
                'identified', self.__class__.identified.string)
        return identified + '(%.2f%%) %s' % ((self.share or 0) * 100, name)

    def get_contact(self):
        return self.party

    def get_sender(self):
        return None


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    beneficiary_definition = fields.Function(
        fields.Many2One('claim.beneficiary', 'Beneficiary Definition'),
        'get_beneficiary_definition')

    def get_beneficiary_definition(self, name):
        return self.service.get_beneficiary_definition_from_party(
            self.beneficiary) if self.service else None

    def invoice_line_description(self):
        return u'%s - %s- %s - %s' % (
            self.service.loss.covered_person.rec_name
            if self.service.loss.covered_person
            else self.service.loss.claim.claimant.rec_name,
            self.service.loss.rec_name,
            coog_string.translate_value(self, 'start_date')
            if self.start_date else '',
            coog_string.translate_value(self, 'end_date')
            if self.end_date else '')

    def init_dict_for_rule_engine(self, cur_dict):
        super(Indemnification, self).init_dict_for_rule_engine(cur_dict)
        beneficiary = self.get_beneficiary_definition(None)
        if beneficiary:
            cur_dict['beneficiary_definition'] = beneficiary

    @classmethod
    def _group_by_duplicate(cls, indemnification):
        return indemnification.service.loss.covered_person

    @classmethod
    def _get_covered_domain(cls, party):
        return [('loss.covered_person', '=', party)]


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['claim.beneficiary']
