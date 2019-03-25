# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby
from sql.conditionals import Coalesce

from trytond.rpc import RPC
from trytond.pyson import Eval, Bool, Or, If
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import Unique
from trytond.cache import Cache
from trytond.server_context import ServerContext
from trytond.tools import grouped_slice

from trytond.modules.coog_core import model, utils, fields, export, coog_string
from trytond.modules.report_engine import Printable
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.offered.extra_data import with_extra_data


__all__ = [
    'Claim',
    'Loss',
    'ClaimService',
    'ClaimSubStatus',
    'ClaimServiceExtraDataRevision',
    ]

CLAIMSTATUSES = [
    ('open', 'Open'),
    ('closed', 'Closed'),
    ('reopened', 'Reopened'),
    ]

CLAIM_READONLY = Bool(Eval('claim_status')) & (
            Eval('claim_status') == 'closed')


class Claim(Printable, model.CoogView):
    'Claim'

    __name__ = 'claim'
    _func_key = 'name'

    name = fields.Char('Number', select=True, states={'readonly': True},
        required=True)
    status = fields.Selection(CLAIMSTATUSES, 'Status', sort=False,
        states={'readonly': True})
    status_string = status.translated('status')
    sub_status = fields.Many2One('claim.sub_status', 'Details on status',
        states={
            'required': Bool(Eval('is_sub_status_required')),
            },
        domain=[('status', '=', Eval('status'))], ondelete='RESTRICT',
        depends=['status', 'is_sub_status_required'])
    is_sub_status_required = fields.Function(
        fields.Boolean('Is Sub Status Required', depends=['status']),
        'on_change_with_is_sub_status_required')
    declaration_date = fields.Date('Declaration Date', required=True)
    end_date = fields.Date('End Date', readonly=True,
        states={'invisible': Eval('status') != 'closed'},
        depends=['status'])
    claimant = fields.Many2One('party.party', 'Claimant', ondelete='RESTRICT',
        required=True, select=True)
    losses = fields.One2Many('claim.loss', 'claim', 'Losses',
        delete_missing=True)
    company = fields.Many2One('company.company', 'Company',
        ondelete='RESTRICT')
    delivered_services = fields.Function(
        fields.One2Many('claim.service', None, 'Claim Services'),
        'get_delivered_services', setter='set_delivered_services')

    # The Main contract is only used to ease the declaration process for 80%
    # of the claims where there is only one contract involved. This link should
    # not be used for other reason than initiating sub elements on claim.
    # Otherwise use claim.get_contract()
    main_contract = fields.Many2One('contract', 'Main Contract',
        ondelete='RESTRICT', domain=[
            ('id', 'in', Eval('possible_contracts')),
            ('company', '=', Eval('company'))],
        depends=['possible_contracts', 'company'])
    possible_contracts = fields.Function(
        fields.Many2Many('contract', None, None, 'Contracts'),
        'on_change_with_possible_contracts')
    _claim_number_generator_cache = Cache('claim_number_generator')
    losses_description = fields.Function(
        fields.Char('Losses Description'), 'get_losses_description')
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._error_messages.update({
                'no_main_contract': 'Impossible to find a main contract, '
                'please try again once it has been set',
                'invalid_declaration_date': 'Declaration date cannot be '
                'in the future, or posterior to the claim\'s creation date',
                'loss_desc_mixin': 'You can not close multiple claims '
                'with different loss descriptions at the same time',
                'contract_will_be_held': 'The contract %(contract)s will be '
                'held with the sub-status %(substatus)s for the payer '
                '%(payer)s.'
                })
        cls._order.insert(0, ('last_modification', 'DESC'))
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.name), 'The number must be unique!'),
            ]
        cls._buttons.update({
                'deliver': {},
                'button_close': {
                    'invisible': Eval('status') == 'closed'},
                })
        cls.__rpc__.update({
                'ws_add_new_loss': RPC(instantiate=0, readonly=False),
                'ws_deliver_automatic_benefit': RPC(
                    instantiate=0, readonly=False),
                })

    @classmethod
    def __post_setup__(cls):
        super(Claim, cls).__post_setup__()
        cls.set_fields_readonly_condition(Eval('status') == 'closed',
            ['status'], cls._get_skip_set_readonly_fields())

    @classmethod
    def _export_light(cls):
        return super(Claim, cls)._export_light() | {'company', 'main_contract',
            'claimant', 'sub_status'}

    @classmethod
    def _export_skips(cls):
        return super(Claim, cls)._export_skips() | {'attachments'}

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return []

    @classmethod
    def view_attributes(cls):
        return super(Claim, cls).view_attributes() + [(
                '/form/group[@id="contracts"]',
                'states',
                {'invisible': True}),
            (
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True}
            )]

    def get_rec_name(self, name):
        res = super(Claim, self).get_rec_name(name)
        if self.claimant:
            res += ' %s' % self.claimant.rec_name
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        op = 'AND' if clause[1] == '!=' or clause[1].startswith('not') else 'OR'
        return [op,
            ('name',) + tuple(clause[1:]),
            ('claimant.rec_name',) + tuple(clause[1:]),
            ]

    def get_synthesis_rec_name(self, name):
        if not self.losses:
            return self.rec_name
        return ', '.join([x.rec_name for x in self.losses])

    def get_icon(self, name=None):
        if 'open' in self.status:
            return 'flash_blue'
        return 'claim'

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    @staticmethod
    def order_last_modification(tables):
        table, _ = tables[None]
        return [Coalesce(table.write_date, table.create_date)]

    @classmethod
    def validate(cls, claims):
        super(Claim, cls).validate(claims)
        cls.check_declaration_date(claims)

    @classmethod
    def check_declaration_date(cls, claims):
        for claim in claims:
            if claim.declaration_date > min(claim.create_date.date(),
                    utils.today()):
                claim.raise_user_error('invalid_declaration_date')

    @fields.depends('status')
    def on_change_with_is_sub_status_required(self, name=None):
        return self.status == 'closed'

    def get_delivered_services(self, name):
        return [service.id for loss in self.losses for service in loss.services]

    @classmethod
    def set_delivered_services(cls, claims, name, value):
        pool = Pool()
        Service = pool.get('claim.service')
        to_delete = []
        for action in value:
            if action[0] == 'write':
                Service.write([Service(id_) for id_ in action[1]], action[2])
            elif action[0] == 'delete':
                to_delete.extend([Service(id_) for id_ in action[1]])
        if to_delete:
            Service.delete(to_delete)

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['name']

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    def is_open(self):
        return self.status in ['open', 'reopened']

    def update_services_extra_data(self):
        pool = Pool()
        Service = pool.get('claim.service')
        to_save = []
        for loss in self.losses:
            for service in loss.services:
                service.on_change_extra_data()
                to_save.append(service)
        Service.save(to_save)

    @staticmethod
    def default_declaration_date():
        return utils.today()

    def get_main_contact(self):
        return self.claimant

    @classmethod
    def create(cls, vlist):
        cls.set_claim_number(vlist)
        return super(Claim, cls).create(vlist)

    @classmethod
    def set_claim_number(cls, items):
        '''
        Assigns a unique name attribute to each item.
        param items a list of dictionnaries or claim instances
        '''
        Generator = Pool().get('ir.sequence')
        gen_id = cls._claim_number_generator_cache.get('generator',
            default=None)
        if not gen_id:
            gen_id = Generator.search([('code', '=', 'claim')], limit=1)[0].id
            cls._claim_number_generator_cache.set('generator', gen_id)

        for i in items:
            if isinstance(i, dict):
                if not i.get('name', None):
                    i['name'] = Generator.get_id(gen_id)
            elif isinstance(i, cls):
                if not i.name:
                    i.name = Generator.get_id(gen_id)

    @classmethod
    def hold_contracts(cls, payers, sub_status):
        pool = Pool()
        Contract = pool.get('contract')
        Party = pool.get('party.party')
        to_suspend = Party.get_depending_contracts(payers)
        # Warn user that the contract will be held
        for contract in to_suspend:
            cls.raise_user_warning(
                'contract_will_be_held_%s' % str(contract),
                'contract_will_be_held', {
                    'contract': contract.rec_name,
                    'payer': contract.payer.rec_name,
                    'substatus': sub_status.rec_name,
                    })
        if to_suspend:
            Contract.hold(to_suspend, sub_status)

    def get_contact(self):
        return self.claimant

    def get_sender(self):
        return None

    @staticmethod
    def default_status():
        return 'open'

    @classmethod
    @model.CoogView.button_action('claim.act_close_claim_wizard')
    def button_close(cls, claims):
        pass

    @classmethod
    def close(cls, claims, sub_status, date=None):
        for claim in claims:
            claim.close_claim(sub_status, date)
        cls.save(claims)

    def close_claim(self, sub_status, date=None):
        self.status = 'closed'
        self.sub_status = sub_status
        self.end_date = date or utils.today()
        for loss in self.losses:
            loss.close(sub_status, date)

    def reopen_claim(self):
        if self.status == 'closed':
            self.status = 'reopened'
            self.sub_status = None
            self.end_date = None

    @fields.depends('claimant', 'declaration_date', 'main_contract',
        'possible_contracts', 'losses')
    def on_change_claimant(self):
        if self.claimant is None:
            self.possible_contracts = []
        else:
            self.possible_contracts = self.get_possible_contracts()
        main_contract = None
        if len(self.possible_contracts) == 1:
            main_contract = self.possible_contracts[0]
        self.main_contract = main_contract

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = min([l.start_date for l in self.losses if l.start_date] or
                [self.declaration_date])
        Contract = Pool().get('contract')
        return Contract.get_covered_contracts_from_party(self.claimant,
            at_date)

    @fields.depends('claimant', 'declaration_date', 'losses')
    def on_change_with_possible_contracts(self, name=None):
        if self.claimant:
            return [x.id for x in self.get_possible_contracts()]
        return []

    def get_contracts(self):
        res = []
        for loss in self.losses:
            res.extend(loss.get_contracts())
        if not res and self.main_contract:
            res.append(self.main_contract)
        return list(set(res))

    def get_contract(self):
        contracts = self.get_contracts()
        if len(contracts) == 1:
            return contracts[0]
        elif len(contracts) > 1 and self.main_contract in contracts:
            return self.main_contract

    def get_product(self):
        return self.get_contract().offered

    @classmethod
    @model.CoogView.button_action('claim.act_deliver_wizard')
    def deliver(cls, claims):
        pass

    @classmethod
    def draft_losses(cls, claims):
        Pool().get('claim.loss').draft(sum([list(x.losses) for x in claims],
                []))

    @classmethod
    def activate_losses(cls, claims):
        Pool().get('claim.loss').activate(sum([list(x.losses) for x in claims],
                []))

    @classmethod
    def deliver_automatic_benefit(cls, claims):
        to_save = []
        for claim in claims:
            changed = False
            for loss in claim.losses:
                if loss.state != 'active':
                    continue
                deliver = [service.benefit for service in loss.services]
                for benefit, option in \
                        loss.covered_benefit_and_options():
                    if (benefit in deliver or
                            not benefit.automatically_deliver):
                        continue
                    loss.init_services(option, [benefit])
                    changed = True
            if changed:
                claim.losses = list(claim.losses)
                to_save.append(claim)
        cls.save(to_save)

    def add_new_loss(self, loss_desc_code=None, only_if_empty=False, **kwargs):
        if only_if_empty:
            if any(x.loss_desc.code == loss_desc_code or not loss_desc_code
                    for x in self.losses if x.loss_desc):
                return
        loss = Pool().get('claim.loss')()
        loss.claim = self
        loss.init_loss(loss_desc_code, **kwargs)
        self.losses = self.losses + (loss, )

    def ws_add_new_loss(self, loss_desc_code, parameters=None, activate=True):
        self.add_new_loss(loss_desc_code, **parameters)
        self.save()
        if activate is True:
            self.activate_losses([self])

    @classmethod
    def ws_deliver_automatic_benefit(cls, claims):
        cls.deliver_automatic_benefit(claims)

    def get_losses_description(self, name):
        return ' - '.join([loss.rec_name for loss in self.losses])

    def get_gdpr_data(self):
        return {
            coog_string.translate_label(self, 'losses'): [
                x.get_gdpr_data() for x in self.losses],
            }


class Loss(model.CoogSQL, model.CoogView,
        with_extra_data(['loss'], schema='loss_desc')):
    'Loss'

    __name__ = 'claim.loss'
    _func_key = 'func_key'

    claim_status = fields.Function(fields.Char('Claim Status'),
        'get_claim_status')
    claim = fields.Many2One('claim', 'Claim', ondelete='CASCADE',
        required=True, select=True)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active')],
        'State', required=True, readonly=True)
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Descriptor',
        ondelete='RESTRICT', states={
            'required': Eval('state') != 'draft',
            'readonly': CLAIM_READONLY,
            },
        domain=[('id', 'in', Eval('possible_loss_descs'))],
        depends=['possible_loss_descs', 'state', 'claim_status'])
    possible_loss_descs = fields.Function(
        fields.Many2Many('benefit.loss.description', None, None,
            'Possible Loss Descs', ),
        'on_change_with_possible_loss_descs')
    event_desc = fields.Many2One('benefit.event.description', 'Event',
        states={
            'required': Eval('state') != 'draft',
            'readonly': CLAIM_READONLY,
            },
        domain=[('loss_descs', '=', Eval('loss_desc'))],
        depends=['loss_desc', 'state', 'claim_status'], ondelete='RESTRICT')
    services = fields.One2Many(
        'claim.service', 'loss', 'Claim Services', delete_missing=True,
        target_not_required=True, domain=[
            ('benefit.loss_descs', '=', Eval('loss_desc')),
            ['OR', ('option', '=', None),
                ('option.coverage.benefits.loss_descs', '=',
                    Eval('loss_desc'))]], depends=['loss_desc'])
    multi_level_view = fields.One2Many('claim.service',
        'loss', 'Claim Services', target_not_required=True,
        delete_missing=True)
    start_date = fields.Date('Loss Date',
        help='Date of the event, or start date of a period',
        states={'readonly': CLAIM_READONLY, }, depends=['claim_status'])
    has_end_date = fields.Function(
        fields.Boolean('With End Date'), 'getter_has_end_date')
    end_date = fields.Date('End Date',
        states={
            'invisible': Bool(~Eval('has_end_date')),
            'readonly': Eval('claim_status') == 'closed',
            }, depends=['has_end_date', 'claim_status'])
    loss_desc_code = fields.Function(
        fields.Char('Loss Desc Code', depends=['loss_desc']),
        'get_loss_desc_code')
    loss_desc_kind = fields.Function(
        fields.Char('Loss Desc Kind', depends=['loss_desc']),
        loader='load_loss_desc_kind', searcher='search_loss_desc_kind')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    available_closing_reasons = fields.Function(
        fields.One2Many('claim.closing_reason', None,
            'Available Closing Reason'),
        'on_change_with_available_closing_reasons')
    closing_reason = fields.Many2One('claim.closing_reason', 'Closing Reason',
        domain=[('id', 'in', Eval('available_closing_reasons'))],
        states={
            'readonly': Eval('claim_status') == 'closed',
            'invisible': ~Eval('has_end_date')},
        depends=['available_closing_reasons', 'claim_status', 'has_end_date'],
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'end_date_smaller_than_start_date':
                'End Date is smaller than start date',
                'duplicate_loss': 'The loss %(loss)s could be a duplicate '
                'of:\n\n%(losses)s',
                'prior_declaration_date': 'Declaration date '
                '%(declaration_date)s is prior to start date %(start_date)s',
                'no_loss_desc_found': 'No loss description found with the '
                'code "%(loss_desc_code)s" in the configuration',
                'no_event_description_on_loss_desc': 'There is no event '
                'description for the loss description "%(loss_desc)s" '
                'in the configuration',
                'no_end_date': 'Missing end date for loss\n%(loss)s,\n',
                })
        cls._buttons.update({
                'draft': {
                    'readonly': Or(
                        CLAIM_READONLY,
                        Eval('state') == 'draft'),
                    'invisible': Or(
                        Eval('state') == 'draft',
                        Eval('claim_status') == 'closed'),
                    },
                'activate': {
                    'invisible': Or(
                        Eval('state') == 'active',
                        ~Eval('loss_desc')),
                    'readonly': Or(
                        CLAIM_READONLY,
                        Eval('state') == 'active',
                        ~Eval('loss_desc')),
                    },
                })

    @classmethod
    def __post_setup__(cls):
        super(Loss, cls).__post_setup__()
        cls.set_fields_readonly_condition(Eval('state') != 'draft',
            ['state'], cls._get_skip_set_readonly_fields())

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return ['end_date', 'closing_reason']

    @classmethod
    def default_state(cls):
        return 'draft'

    def on_change_with_closing_reason(self, name=None):
        pass

    def get_claim_status(self, name=None):
        if self.claim:
            return self.claim.status

    @fields.depends('loss_desc')
    def on_change_with_available_closing_reasons(self, name=None):
        if self.loss_desc:
            return [x.id for x in self.loss_desc.closing_reasons]

    @fields.depends('claim', 'event_desc', 'loss_desc', 'start_date')
    def on_change_with_possible_loss_descs(self, name=None):
        pool = Pool()
        LossDesc = pool.get('benefit.loss.description')
        res = []
        if not self.claim:
            return res
        if not self.claim.main_contract:
            return [x.id for x in LossDesc.search([])]
        for benefit, option in self.claim.main_contract.get_possible_benefits(
                self):
            res.extend(benefit.loss_descs)
        return [x.id for x in set(res)]

    def get_func_key(self, name):
        if self.loss_desc:
            return '|'.join([self.claim.name, str(self.get_date()),
                    self.loss_desc.loss_kind])

    def get_loss_desc_code(self, name):
        return self.loss_desc.code if self.loss_desc else ''

    def load_loss_desc_kind(self, name=None):
        return self.loss_desc.loss_kind if self.loss_desc else ''

    @classmethod
    def search_loss_desc_kind(cls, name, clause):
        return [('loss_desc.kind',) + tuple(clause[1:])]

    @fields.depends('event_desc', 'loss_desc', 'has_end_date', 'end_date')
    def on_change_loss_desc(self):
        super(Loss, self).on_change_loss_desc()
        self.has_end_date = self.getter_has_end_date('')
        self.loss_desc_code = self.loss_desc.code if self.loss_desc else ''
        if (self.loss_desc and self.event_desc
                and self.event_desc not in self.loss_desc.event_descs):
            self.event_desc = None
        self.end_date = self.end_date if self.end_date else None

    def get_rec_name(self, name):
        lang = Transaction().language
        Lang = Pool().get('ir.lang')
        lang = Lang.get(lang)
        res = ''
        if self.loss_desc:
            res = self.loss_desc.rec_name
        if self.start_date and not self.end_date:
            res += ' [%s]' % lang.strftime(self.start_date, '%d/%m/%Y')
        elif self.start_date and self.end_date:
            res += ' [%s - %s]' % (
                lang.strftime(self.start_date, '%d/%m/%Y'),
                lang.strftime(self.end_date, '%d/%m/%Y'))
        return res

    def get_summary(self):
        return self.rec_name

    @classmethod
    def get_date_field_for_kind(cls, kind):
        return 'start_date'

    def getter_has_end_date(self, name=None):
        return self.loss_desc and self.loss_desc.has_end_date

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if not clause[2]:
            return [('id', '=', None)]
        operands = clause[2].split('|')
        if len(operands) == 3:
            claim_name, date_str, kind = operands
            res = []
            date_field = cls.get_date_field_for_kind(kind)
            res.append(('claim.name', clause[1], claim_name))
            res.append((date_field, clause[1],
                    datetime.datetime.strptime(date_str, '%Y-%m-%d').date()))
            res.append(('loss_desc.loss_kind', clause[1], kind))
            return res
        else:
            return [('id', '=', None)]

    @classmethod
    def add_func_key(cls, values):
        # Update without func_key is not handled for now
        values['_func_key'] = None

    @classmethod
    def _export_light(cls):
        return super(Loss, cls)._export_light() | {'loss_desc', 'event_desc'}

    @classmethod
    def _export_skips(cls):
        return super(Loss, cls)._export_skips() | {'multi_level_view'}

    def check_end_date(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            self.raise_user_error('end_date_smaller_than_start_date')

    def init_service(self, option, benefit):
        service = Pool().get('claim.service')()
        service.init_from_option(option)
        service.init_from_loss(self, benefit)
        return service

    def init_services(self, option, benefits):
        if (not hasattr(self, 'services')
                or not self.services):
            self.services = []
        else:
            self.services = list(self.services)
        for benefit in benefits:
            del_service = None
            if not benefit.several_delivered:
                for other_del_service in self.services:
                    if (other_del_service.benefit == benefit
                            and other_del_service.option == option):
                        del_service = other_del_service
                if del_service:
                    continue

            service = self.init_service(option, benefit)
            if service:
                self.services = self.services + (service,)

    def init_loss(self, loss_desc_code=None, **kwargs):
        pool = Pool()
        if loss_desc_code:
            LossDesc = pool.get('benefit.loss.description')
            self.loss_desc, = LossDesc.search([('code', '=', loss_desc_code)])
            self.event_desc = self.loss_desc.event_descs[0]
            self.extra_data = self.loss_desc.refresh_extra_data({})
        else:
            self.loss_desc = None
        if not kwargs:
            return
        for arg, value in kwargs.items():
            setattr(self, arg, value)

    def get_contracts(self):
        return list(set([x.contract for x in self.services]))

    def close(self, sub_status, date=None):
        pass

    @property
    def loss(self):
        if self.loss_desc:
            return getattr(self, self.loss_desc.loss_kind + '_loss')

    def get_date(self):
        return self.start_date if hasattr(self, 'start_date') else None

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['claim'] = self.claim
        cur_dict['loss'] = self

    @classmethod
    def validate(cls, instances):
        with model.error_manager():
            super(Loss, cls).validate(instances)
            for instance in instances:
                instance.check_end_date()
                if instance.has_end_date and instance.end_date is None \
                        and instance.closing_reason:
                    cls.append_functional_error('no_end_date',
                        {'loss': instance.rec_name})

    def get_possible_duplicates(self):
        if not self.do_check_duplicates():
            return []
        for key in self.get_possible_duplicates_fields():
            if not getattr(self, key, None):
                return []
        return self.search(self.get_possible_duplicates_clauses())

    @classmethod
    def get_possible_duplicates_fields(cls):
        return {'loss_desc', 'start_date'}

    def get_possible_duplicates_clauses(self):
        clause = [
            ('id', '!=', self.id),
            ('start_date', '=', self.start_date),
            ]
        if self.loss_desc:
            clause += ('loss_desc', '=', self.loss_desc.id),
        return clause

    @classmethod
    def do_check_duplicates(cls):
        return False

    def covered_options(self):
        Option = Pool().get('contract.option')
        return Option.get_covered_options_from_party(self.claim.claimant,
            self.get_date() or self.claim.declaration_date)

    def covered_benefit_and_options(self):
        options = self.covered_options()
        res = []
        for option in options:
            res.extend(option.get_possible_benefits(self))
        return res

    @classmethod
    @model.CoogView.button
    def draft(cls, losses):
        to_write = [x for x in losses if x.state != 'draft']
        if to_write:
            cls.write(to_write, {'state': 'draft'})
            Pool().get('event').notify_events(to_write, 'draft_loss')

    def check_activation(self):
        claim = self.claim
        Lang = Pool().get('ir.lang')
        if claim.losses:
            start_dates = [x.start_date for x in claim.losses
                if x.start_date]
            start_dates.sort()
            if start_dates and start_dates[0] > claim.declaration_date:
                lang = Transaction().context.get('language')
                Lang = Pool().get('ir.lang')
                lang = Lang.get(lang)
                self.raise_user_warning('prior_declaration_date_%s' %
                    str(self.id), 'prior_declaration_date', {
                        'declaration_date': lang.strftime(
                            claim.declaration_date,
                            lang.date),
                        'start_date': lang.strftime(start_dates[0],
                            lang.date),
                        })
        duplicates = self.get_possible_duplicates()
        if not duplicates:
            return
        self.raise_user_warning('possible_duplicates_%s' % str(self.id),
            'duplicate_loss', {'loss': self.rec_name,
                'losses': '\n'.join(x.rec_name for x in duplicates)})

    @classmethod
    @model.CoogView.button
    def activate(cls, losses):
        pool = Pool()
        to_write = [x for x in losses if x.state != 'active']
        if to_write:
            with model.error_manager():
                for loss in to_write:
                    loss.check_activation()
            cls.write(to_write, {'state': 'active'})
            covered_to_hold_contracts = list({
                    (x.covered_person, x.loss_desc.contract_hold_sub_status)
                    for x in losses if x.loss_desc.contract_hold_sub_status
                    and x.covered_person
                    })

            def _group_by_sub_status(obj):
                return obj[1]

            if covered_to_hold_contracts:
                Claim = pool.get('claim')
                covered_to_hold_contracts = sorted(covered_to_hold_contracts,
                    key=_group_by_sub_status)
                for sub_status, payers in groupby(covered_to_hold_contracts,
                        key=_group_by_sub_status):
                    Claim.hold_contracts([x[0] for x in payers], sub_status)
            pool.get('event').notify_events(to_write, 'activate_loss')

    @fields.depends('start_date', 'claim', 'claimant', 'declaration_date',
        'losses')
    def on_change_start_date(self):
        if self.claim:
            self.claim.possible_contracts = \
                self.claim.on_change_with_possible_contracts()

    def get_gdpr_data(self):
        Party = Pool().get('party.party')
        label_ = Party._label_gdpr
        value_ = coog_string.translate_value
        return {
            label_(self, 'loss_desc'):
                value_(self.loss_desc, 'name'),
            label_(self, 'start_date'):
                value_(self, 'start_date'),
            label_(self, 'end_date'):
                value_(self, 'end_date'),
            label_(self, 'event_desc'):
                value_(self.event_desc, 'name'),
            }


class ClaimService(model.CoogSQL, model.CoogView,
        with_extra_data(['benefit'], schema='benefit',
            field_name='current_extra_data',
            getter_name='getter_current_extra_data',
            setter_name='setter_void'),
        ModelCurrency):
    'Claim Service'
    __name__ = 'claim.service'

    contract = fields.Many2One('contract', 'Contract', ondelete='RESTRICT',
        readonly=True)
    option = fields.Many2One(
        'contract.option', 'Coverage', ondelete='RESTRICT', readonly=True)
    theoretical_covered_element = fields.Function(
        fields.Many2One('contract.covered_element',
            'Theoretical Covered Element'),
        'get_theoretical_covered_element')
    loss = fields.Many2One('claim.loss', 'Loss',
        ondelete='CASCADE', select=True, required=True)
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT',
        required=True, readonly=True)
    extra_datas = fields.One2Many('claim.service.extra_data', 'claim_service',
        'Extra Data', delete_missing=True,
        states={
            'invisible': ~Eval('extra_datas'),
            }, depends=['extra_datas'])
    origin_service = fields.Many2One('claim.service', 'Origin Service',
        ondelete='RESTRICT', readonly=True, states={
            'invisible': ~Eval('may_have_origin'),
            },
        domain=[If(~Eval('may_have_origin'), [('id', '=', None)], [])],
        depends=['may_have_origin'],
        help='This can be used to know if this service is some sort of '
        'follow-up of the parent. For instance if the contract from which the '
        'origin service was terminated and replaced with another which '
        'created this service')
    claim = fields.Function(
        fields.Many2One('claim', 'Claim'),
        'getter_claim', searcher='search_claim')
    summary = fields.Function(
        fields.Text('Service Summary'),
        'get_summary')
    loss_summary = fields.Function(
        fields.Text('Loss Summary'),
        'get_loss_summary')
    benefit_summary = fields.Function(
        fields.Text('Benefit Summary'),
        'get_benefit_summary')
    insurer_delegations = fields.Function(
        fields.Char('Insurer Delefations', states={
                'invisible': ~Eval('insurer_delegations'),
                'field_color_red': True}),
        'on_change_with_insurer_delegations')
    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    claim_status = fields.Function(fields.Char('Claim Status'),
        'get_claim_status')
    may_have_origin = fields.Function(
        fields.Boolean('May Have Origin'),
        'getter_may_have_origin')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'button_set_origin_service': {
                    'invisible': ~~Eval('origin_service') | (
                        Eval('claim_status', 'closed') == 'closed'),
                    'readonly': ~~Eval('origin_service') | (
                        Eval('claim_status', 'closed') == 'closed'),
                    },
                'clear_origin_service': {
                    'invisible': ~Eval('origin_service') | (
                        Eval('claim_status', 'closed') == 'closed'),
                    'readonly': ~Eval('origin_service') | (
                        Eval('claim_status', 'closed') == 'closed'),
                    },
                })

    @classmethod
    def __post_setup__(cls):
        super(ClaimService, cls).__post_setup__()
        cls.set_fields_readonly_condition(Eval('claim_status') == 'closed',
            ['claim_status'], cls._get_skip_set_readonly_fields())
        Pool().get('extra_data')._register_extra_data_provider(cls,
            'find_extra_data_value', ['benefit'])

    def get_theoretical_covered_element(self, name):
        return None

    def getter_current_extra_data(self, name):
        return self.get_service_extra_data(utils.today())

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return []

    @classmethod
    def _export_light(cls):
        return super(ClaimService, cls)._export_light() | {'contract',
            'option', 'benefit'}

    def get_claim_status(self, name):
        if self.claim:
            return self.claim.status

    @classmethod
    def getter_claim(cls, instances, name):
        loss = Pool().get('claim.loss').__table__()
        table = cls.__table__()

        result = {x.id: None for x in instances}
        cursor = Transaction().connection.cursor()
        query = table.join(loss, 'LEFT OUTER',
            condition=table.loss == loss.id
            )

        for cur_slice in grouped_slice(instances):
            cursor.execute(*query.select(table.id, loss.claim,
                    where=table.id.in_([x.id for x in cur_slice])
                    ))

            for table_id, value in cursor.fetchall():
                result[table_id] = value

        return result

    def getter_may_have_origin(self, name):
        return self.benefit.may_have_origin

    def get_icon(self, name):
        if self.insurer_delegations:
            return 'tryton-dialog-warning'

    @classmethod
    def search_claim(cls, name, clause):
        return [('loss.claim',) + tuple(clause[1:])]

    @fields.depends('benefit', 'extra_datas')
    def on_change_extra_datas(self):
        pool = Pool()
        ExtraData = pool.get('claim.service.extra_data')

        if not self.benefit:
            self.extra_datas = []
            return

        if not self.extra_datas:
            self.extra_datas = [
                ExtraData(extra_data_values={}, date=None)]
        else:
            self.extra_datas = self.extra_datas

        data_values = self.benefit.refresh_extra_data(
            self.extra_datas[-1].extra_data_values)

        self.extra_datas[-1].extra_data_values = data_values

    def get_insurer(self):
        date = self.loss.get_date() if self.loss else None
        return self.option.coverage.get_insurer(date) if self.option else None

    @fields.depends('option', 'loss')
    def on_change_with_insurer_delegations(self, name=None):
        '''
            Returns a string with the translated name of all granted claim
            related delegations
        '''
        insurer = self.get_insurer()
        if not insurer:
            return ''
        pool = Pool()
        InsurerDelegation = pool.get('insurer.delegation')
        Translation = pool.get('ir.translation')
        fnames = [x for x in InsurerDelegation._delegation_flags
            if x.startswith('claim_')]
        delegation = insurer.get_delegation(
            self.option.coverage.insurance_kind)
        values = [Translation.get_source('insurer.delegation,' + x,
                'field', Transaction().language, None)
            or InsurerDelegation._fields[x].string
            for x in fnames if not getattr(delegation, x)]
        return ', '.join(values)

    def get_rec_name(self, name):
        res = ''
        if self.loss:
            res += self.loss.rec_name
        if self.benefit:
            res += ' - ' + self.benefit.rec_name
        return res

    def get_summary(self, name=None):
        res = ''
        if self.contract.subscriber != self.claim.claimant:
            res = '%s - ' % self.contract.subscriber.rec_name
        if self.option and self.get_insurer():
            res += '%s [%s] - %s' % (self.contract.rec_name,
                self.contract.product.rec_name, self.get_insurer())
        else:
            res += self.contract.get_synthesis_rec_name()
        return res

    def get_benefit_summary(self, name):
        return '%s (%s)' % (self.benefit.rec_name,
            self.get_insurer().rec_name)

    def get_loss_summary(self, name=None):
        if self.loss:
            return self.loss.rec_name

    @classmethod
    def add_func_key(cls, values):
        # Update is not handled for now
        values['_func_key'] = None

    def init_from_loss(self, loss, benefit):
        self.loss = loss
        self.benefit = benefit
        self.theoretical_covered_element = \
            self.get_theoretical_covered_element(None)
        self.on_change_extra_datas()

    def init_from_option(self, option):
        self.option = option
        self.contract = option.parent_contract

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['service'] = self
        self.benefit.init_dict_for_rule_engine(cur_dict)
        self.loss.init_dict_for_rule_engine(cur_dict)
        if self.option:
            self.option.init_dict_for_rule_engine(cur_dict)
        elif self.contract:
            self.contract.init_dict_for_rule_engine(cur_dict)
        if self.theoretical_covered_element:
            cur_dict['covered_element'] = self.theoretical_covered_element

    def get_currency(self):
        if self.option:
            return self.option.get_currency()

    def get_service_extra_data(self, at_date):
        """
        This method should not be modified, it is specific to only pickup
        service's extra datas and may be used outside the code (In reports
        templates for instance)
        """
        extra_data = utils.get_value_at_date(self.extra_datas, at_date)
        return extra_data.extra_data_values if extra_data else {}

    def get_beneficiaries_data(self, at_date):
        # Returns a list of beneficiaries with their associated share
        if self.benefit.beneficiary_kind == 'other':
            return []
        if self.benefit.beneficiary_kind == 'subscriber':
            return [(self.option.parent_contract.subscriber, 1)]

    def update_extra_data(self, at_date, base_values):
        ExtraData = Pool().get('claim.service.extra_data')
        extra_data = utils.get_value_at_date(self.extra_datas, at_date)
        with ServerContext().set_context(service=self):
            new_data = self.benefit.refresh_extra_data(
                extra_data.extra_data_values)

        # Only use matching extra_data
        values = {x: base_values.get(x, None)
            for x in list(extra_data.extra_data_values.keys()) +
                    list(new_data.keys())}
        if (extra_data.extra_data_values != values):
            if (at_date == extra_data.date or
                    at_date == self.loss.start_date and not extra_data.date):
                extra_data.extra_data_values = values
                self.extra_datas = self.extra_datas
            else:
                extra_data = ExtraData(extra_data_values=values, date=at_date)
                self.extra_datas = [x for x in self.extra_datas
                    if not x.date or x.date < at_date] + [extra_data]

    def find_extra_data_value(self, name, **kwargs):
        extra_data = utils.get_value_at_date(self.extra_datas, kwargs.get(
                'date', utils.today()))
        return extra_data.find_extra_data_values_value(name, **kwargs)

    @classmethod
    @model.CoogView.button_action('claim.act_set_origin_service')
    def button_set_origin_service(cls, services):
        pass

    def set_origin_service(self, origin):
        assert origin
        assert self.loss.claim.status != 'closed'
        self.origin_service = origin
        self.save()

    @classmethod
    @model.CoogView.button
    def clear_origin_service(cls, services):
        with model.error_manager():
            for service in services:
                if not service.origin_service:
                    cls.append_functional_error('clearing_empty_origin',
                        {'service': service.rec_name})
        cls.raise_user_warning('clearing_origin_%s' % ','.join(
                str(x.id) for x in services[:10]),
            'clearing_origin')
        for service in services:
            assert service.loss.claim.status != 'closed'
            service._clear_origin_service()
        cls.save(services)

    def _clear_origin_service(self):
        self.origin_service = None


class ClaimSubStatus(model.CoogSQL, model.CoogView):
    'Claim Close Reason'

    __name__ = 'claim.sub_status'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    status = fields.Selection(CLAIMSTATUSES, 'Status', required=True,
        select=True)
    active = fields.Boolean('Active')

    _get_claim_sub_status_cache = Cache('get_claim_sub_status')

    @classmethod
    def __setup__(cls):
        super(ClaimSubStatus, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls._error_messages.update({
                'no_sub_status_found': 'No sub status has been found with the '
                'code %s.'
                })

    @classmethod
    def create(cls, vlist):
        created = super(ClaimSubStatus, cls).create(vlist)
        cls._get_claim_sub_status_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(ClaimSubStatus, cls).delete(ids)
        cls._get_claim_sub_status_cache.clear()

    @classmethod
    def write(cls, *args):
        super(ClaimSubStatus, cls).write(*args)
        cls._get_claim_sub_status_cache.clear()

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def get_sub_status(cls, code):
        sub_status_id = cls._get_claim_sub_status_cache.get(code, default=-1)
        if sub_status_id != -1:
            return cls(sub_status_id)
        instances = cls.search([('code', '=', code)])
        if len(instances) != 1:
            cls.raise_user_error('no_sub_status_found', code)
        cls._get_claim_sub_status_cache.set(code, instances[0].id)
        return instances[0]


class ClaimServiceExtraDataRevision(model.CoogSQL, model.CoogView,
        with_extra_data(['benefit'], schema='benefit',
            field_name='extra_data_values',
            create_string='extra_data_values_translated',
            create_summary='extra_data_summary'),
        model._RevisionMixin, export.ExportImportMixin):
    'Claim Service Extra Data'

    __name__ = 'claim.service.extra_data'
    _parent_name = 'claim_service'
    _func_key = 'date'

    claim_service = fields.Many2One('claim.service', 'Claim Service',
        required=True, select=True, ondelete='CASCADE')
    claim_status = fields.Function(fields.Char('Claim Status'),
        'get_claim_status')
    benefit = fields.Function(
        fields.Many2One('benefit', 'Benefit'),
        'getter_benefit')

    @classmethod
    def __post_setup__(cls):
        super(ClaimServiceExtraDataRevision, cls).__post_setup__()
        cls.set_fields_readonly_condition(Eval('claim_status') == 'closed',
            ['claim_status'], cls._get_skip_set_readonly_fields())

    @staticmethod
    def revision_columns():
        return ['extra_data_values']

    @classmethod
    def _get_skip_set_readonly_fields(cls):
        return []

    @classmethod
    def get_reverse_field_name(cls):
        return 'extra_data'

    @classmethod
    def add_func_key(cls, values):
        if 'date' in values:
            values['_func_key'] = values['date']
        else:
            values['_func_key'] = None

    @fields.depends('claim_service')
    def on_change_claim_service(self):
        if self.claim_service:
            self.benefit = self.claim_service.benefit
        else:
            self.benefit = None

    def getter_benefit(self, name):
        return self.service.benefit.id

    def get_claim_status(self, name):
        if self.claim_service and self.claim_service.claim:
            return self.claim_service.claim.status
