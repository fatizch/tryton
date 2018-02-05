# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Literal
from sql.aggregate import Max
from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool, In, And, Equal
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.report_engine import Printable

from datetime import timedelta

__all__ = [
    'Claim',
    'ClaimBeneficiary',
    'Loss',
    'ClaimService',
    'ClaimServiceExtraDataRevision',
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
        domain=[If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
                )
            ], depends=['possible_covered_persons'], ondelete='RESTRICT')
    std_start_date = fields.Function(fields.Date('STD Start Date',
            states={'invisible': Eval('loss_desc_kind') != 'std'},
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    std_end_date = fields.Function(fields.Date('STD End Date',
            states={
                'invisible': Eval('loss_desc_kind') != ('std'),
                'readonly': Eval('claim_status') == 'closed',
                 }, depends=['loss_desc_kind', 'loss_desc', 'claim_status']),
        'get_start_end_dates', setter='set_start_end_dates')
    initial_std_start_date = fields.Date('Initial STD Start Date',
        states={'invisible': Eval('loss_desc_kind') != 'ltd',
            'readonly': Eval('state') != 'draft',
            'required': And(Eval('state') != 'draft',
                Eval('loss_desc_kind') == 'ltd')},
        depends=['loss_desc_kind', 'loss_desc', 'state'])
    ltd_start_date = fields.Function(fields.Date('LTD Start Date',
            states={'invisible': Eval('loss_desc_kind') != 'ltd'},
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    ltd_end_date = fields.Function(fields.Date('LTD End Date',
            states={
                'invisible': Eval('loss_desc_kind') != 'ltd',
                'readonly': Eval('claim_status') == 'closed',
                },
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    return_to_work_date = fields.Date('Return to Work',
        states={'invisible': Eval('loss_desc_kind') != 'std'},
        domain=[If(Bool(Eval('return_to_work_date')),
                ('return_to_work_date', '>', Eval('end_date')),
                ())
            ], depends=['end_date'])
    is_a_relapse = fields.Boolean('Is A Relapse',
        states={'invisible': ~Eval('with_end_date')}, depends=['with_end_date'])
    loss_kind = fields.Function(
        fields.Char('Loss Kind'),
        'get_loss_kind')

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls.start_date.states['invisible'] = cls.start_date.states.get(
            'invisible', False) | In(Eval('loss_desc_kind', ''),
            ['std', 'ltd'])
        cls.start_date.depends.append('loss_desc_kind')
        cls.end_date.states['invisible'] = cls.end_date.states.get(
            'invisible', False) | In(Eval('loss_desc_kind', ''),
            ['std', 'ltd'])
        cls.end_date.depends.append('loss_desc_kind')
        cls._error_messages.update({
                'relapse': 'Relapse',
                'missing_previous_loss': 'An inital std must be created in '
                'order to declare a relapse',
                'previous_loss_end_date_missing': "The previous std "
                "doesn't have an end date defined",
                'one_day_between_relapse_and_previous_loss': 'One day is '
                'required between the relapse and the previous std'
                })
        cls.closing_reason.states.update({
                'required': If(Equal(Eval('loss_kind'), 'std'),
                    Bool(Eval('std_end_date')),
                    Bool(Eval('ltd_end_date')))
                })
        cls.closing_reason.depends.extend(['std_end_date', 'ltd_end_date',
                'loss_kind'])

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return super(Loss, cls)._get_skip_set_readonly_fields() + [
            'ltd_end_date', 'std_end_date']

    @fields.depends('loss_kind')
    def on_change_with_possible_loss_descs(self, name=None):
        return super(Loss, self).on_change_with_possible_loss_descs(name)

    def get_loss_kind(self, name):
        if self.loss_desc:
            return self.loss_desc.loss_kind

    def get_start_end_dates(self, name):
        if 'start_date' in name:
            date = 'start_date'
        else:
            date = 'end_date'
        return getattr(self, date, None)

    @classmethod
    def set_start_end_dates(cls, losses, name, value):
        if 'start_date' in name:
            date = 'start_date'
        else:
            date = 'end_date'
        cls.write(losses, {date: value})

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

    @fields.depends('std_end_date', 'ltd_end_date', 'available_closing_reasons')
    def on_change_with_closing_reason(self, name=None):
        super(Loss, self).on_change_with_closing_reason(name)
        if ((self.std_end_date or self.ltd_end_date) and
                len(self.available_closing_reasons) == 1):
            return self.available_closing_reasons[0].id
        if not self.std_end_date and not self.ltd_end_date:
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
        super(Loss, self).init_loss(loss_desc_code, **kwargs)
        self.covered_person = self.claim.claimant \
            if self.claim.claimant.is_person else None
        self.update_end_date()

    @property
    def date(self):
        return self.start_date

    def get_covered_person(self):
        return getattr(self, 'covered_person', None)

    def get_all_extra_data(self, at_date):
        CoveredElement = Pool().get('contract.covered_element')
        res = super(Loss, self).get_all_extra_data(at_date)
        if not self.claim:
            return res
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.covered_person, self.start_date):
            if (covered_element.party and
                    covered_element.party == self.covered_person and
                    covered_element.main_contract == self.claim.main_contract):
                res.update(covered_element.get_all_extra_data(self.start_date))
        return res

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
        if self.claim.losses.index(self) == 0:
            self.append_functional_error('missing_previous_loss')
        if not self.start_date:
            return
        previous_loss = self.claim.losses[
            self.claim.losses.index(self) - 1]
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
        old_values = self.loss.claim.delivered_services[0].extra_datas[-1].\
            extra_data_values
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

    def get_all_extra_data(self, at_date):
        res = super(ClaimService, self).get_all_extra_data(at_date)
        res.update(self.get_service_extra_data(at_date))
        res.update(self.loss.get_all_extra_data(at_date))
        if self.option:
            res.update(self.option.get_all_extra_data(at_date))
        elif self.contract:
            res.update(self.contract.get_all_extra_data(at_date))
        res.update(self.benefit.get_all_extra_data(at_date))
        return res

    def get_beneficiary_definition_from_party(self, party):
        if not self.manual_beneficiaries:
            return None
        for beneficiary in self.beneficiaries:
            if beneficiary.party == party:
                return beneficiary


class ClaimBeneficiary(model.CoogSQL, model.CoogView, Printable):
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
    extra_data_values = fields.Dict('extra_data', 'Extra Data')
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
            possible_services = [x for  x in services if x.can_be_indemnified]
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

    @fields.depends('service', 'extra_data_values')
    def on_change_with_extra_data_values(self):
        if not self.service:
            return []
        if not self.extra_data_values:
            return self.service.benefit.get_beneficiary_extra_data_def(self)
        return self.extra_data_values

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

    def get_all_extra_data(self, at_date):
        res = super(Indemnification, self).get_all_extra_data(at_date)
        beneficiary = self.get_beneficiary_definition(None)
        if beneficiary:
            res.update(beneficiary.extra_data_values)
        return res


class ClaimServiceExtraDataRevision:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service.extra_data'

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        res = super(ClaimServiceExtraDataRevision, cls).get_extra_data_summary(
            extra_datas, name)
        for instance, desc in res.iteritems():
            new_data = {}
            for line in desc.splitlines():
                key, value = line.split(' : ')
                if ' M-' in key:
                    new_key = key.split(' M-')[0]
                    if new_key not in new_data:
                        new_data[new_key] = Decimal(value) \
                            if value != 'None' else 0
                    else:
                        new_data[new_key] += Decimal(value) \
                            if value != 'None' else 0
                else:
                    new_data[key] = value
            res[instance] = '\n'.join(('%s : %s' % (k, v) for k, v in
                    new_data.iteritems()))
        return res


class DocumentRequestLine:
    __metaclass__ = PoolMeta
    __name__ = 'document.request.line'

    @classmethod
    def for_object_models(cls):
        return super(DocumentRequestLine, cls).for_object_models() + \
            ['claim.beneficiary']
