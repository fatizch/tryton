import datetime

from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import Unique
from trytond.cache import Cache

from trytond.modules.cog_utils import model, utils, fields, export, coop_string
from trytond.modules.report_engine import Printable
from trytond.modules.contract import ServiceMixin


__metaclass__ = PoolMeta
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


class Claim(model.CoopSQL, model.CoopView, Printable):
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
            'required': Bool(Eval('is_sub_status_required'))
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
    losses = fields.One2Many('claim.loss', 'claim',
        'Losses', states={'readonly': Eval('status') == 'closed'},
        delete_missing=True)
    company = fields.Many2One('company.company', 'Company',
        ondelete='RESTRICT')
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
        'getter_possible_contracts')
    _claim_number_generator_cache = Cache('claim_number_generator')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._error_messages.update({
                'no_main_contract': 'Impossible to find a main contract, '
                'please try again once it has been set',
                })
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.name), 'The number must be unique!'),
            ]
        cls._buttons.update({
                'deliver': {}
                })

    @classmethod
    def _export_light(cls):
        return super(Claim, cls)._export_light() | {'company', 'main_contract',
            'claimant', 'sub_status'}

    @classmethod
    def _export_skips(cls):
        return super(Claim, cls)._export_skips() | {'attachments'}

    @classmethod
    def view_attributes(cls):
        return super(Claim, cls).view_attributes() + [(
                '/form/group[@id="contracts"]',
                'states',
                {'invisible': True}
                )]

    def get_rec_name(self, name):
        res = super(Claim, self).get_rec_name(name)
        if self.claimant:
            res += ' %s' % self.claimant.rec_name
        return res

    def get_synthesis_rec_name(self, name):
        if not self.losses:
            return self.rec_name
        return ', '.join([x.rec_name for x in self.losses])

    def on_change_with_is_sub_status_required(self, name=None):
        return self.status == 'closed'

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

    def get_contact(self):
        return self.claimant

    def get_sender(self):
        return None

    @staticmethod
    def default_status():
        return 'open'

    @classmethod
    def close(cls, claims, sub_status):
        for claim in claims:
            claim.close_claim(sub_status)
        cls.save(claims)

    def close_claim(self, sub_status):
        self.status = 'closed'
        self.sub_status = sub_status
        self.end_date = utils.today()

    def reopen_claim(self):
        if self.status == 'closed':
            self.status = 'reopened'
            self.sub_status = None
            self.end_date = None

    @fields.depends('claimant', 'declaration_date', 'possible_contracts')
    def on_change_claimant(self):
        self.possible_contracts = self.get_possible_contracts()
        main_contract = None
        if len(self.possible_contracts) == 1:
            main_contract = self.possible_contracts[0]
        self.main_contract = main_contract

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = self.declaration_date
        Contract = Pool().get('contract')
        return Contract.get_possible_contracts_from_party(self.claimant,
            at_date)

    def getter_possible_contracts(self, name=None):
        return [x.id for x in self.get_possible_contracts()]

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
        else:
            self.raise_user_error('no_main_contract')

    def get_product(self):
        return self.get_contract().offered

    @classmethod
    @model.CoopView.button_action('claim.act_deliver_wizard')
    def deliver(cls, claims):
        pass


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'claim.loss'
    _func_key = 'func_key'

    claim = fields.Many2One('claim', 'Claim', ondelete='CASCADE',
        required=True, select=True)
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Descriptor',
        ondelete='RESTRICT', required=True,
        domain=[
                ('id', 'in', Eval('possible_loss_descs')),
                ],
        depends=['possible_loss_descs'])
    possible_loss_descs = fields.Function(
        fields.Many2Many('benefit.loss.description', None, None,
            'Possible Loss Descs', ),
        'on_change_with_possible_loss_descs')
    event_desc = fields.Many2One('benefit.event.description', 'Event',
        domain=[('loss_descs', '=', Eval('loss_desc'))],
        depends=['loss_desc'], ondelete='RESTRICT', required=True)
    services = fields.One2Many(
        'claim.service', 'loss', 'Claim Services', delete_missing=True,
        target_not_required=True, domain=[
            ('benefit.loss_descs', '=', Eval('loss_desc')),
            ['OR', ('option', '=', None),
                ('option.coverage.benefits.loss_descs', '=',
                    Eval('loss_desc'))]],
        depends=['loss_desc'])
    multi_level_view = fields.One2Many('claim.service',
        'loss', 'Claim Services', target_not_required=True)
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('extra_data')})
    start_date = fields.Date('Loss Date')
    with_end_date = fields.Function(
        fields.Boolean('With End Date'), 'get_with_end_date')
    end_date = fields.Date('End Date',
        states={'invisible': Bool(~Eval('with_end_date'))},
        depends=['with_end_date'])
    loss_desc_code = fields.Function(
        fields.Char('Loss Desc Code', depends=['loss_desc']),
        'get_loss_desc_code')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'end_date_smaller_than_start_date':
                'End Date is smaller than start date',
                })

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

    @fields.depends('loss_desc')
    def on_change_with_extra_data(self):
        res = {}
        if self.loss_desc:
            res = utils.init_extra_data(self.loss_desc.extra_data_def)
        return res

    def get_func_key(self, name):
        return '|'.join([self.claim.name, str(self.get_date()),
                self.loss_desc.loss_kind])

    def get_loss_desc_code(self, name):
        return self.loss_desc.code if self.loss_desc else ''

    @fields.depends('event_desc', 'loss_desc', 'with_end_date', 'end_date')
    def on_change_loss_desc(self):
        self.with_end_date = self.get_with_end_date('')
        self.loss_desc_code = self.loss_desc.code if self.loss_desc else ''
        if (self.loss_desc and self.event_desc
                and self.event_desc not in self.loss_desc.event_descs):
            self.event_desc = None
        self.end_date = self.end_date if self.end_date else None

    def get_rec_name(self, name=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Transaction().language
        res = ''
        if self.loss_desc:
            res = self.loss_desc.rec_name
        if self.start_date and not self.end_date:
            res += ' [%s]' % Lang.strftime(self.start_date, lang, '%d/%m/%Y')
        elif self.start_date and self.end_date:
            res += ' [%s - %s]' % (
                Lang.strftime(self.start_date, lang, '%d/%m/%Y'),
                Lang.strftime(self.end_date, lang, '%d/%m/%Y'))
        return res

    @classmethod
    def get_date_field_for_kind(cls, kind):
        return 'start_date'

    def get_with_end_date(self, name=None):
        return self.loss_desc and self.loss_desc.with_end_date

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
            for other_del_service in self.services:
                if (other_del_service.benefit == benefit
                        and other_del_service.option == option):
                    del_service = other_del_service
            if del_service:
                continue

            service = self.init_service(option, benefit)
            if service:
                self.services = self.services + (service,)

    def get_contracts(self):
        return list(set([x.contract for x in self.services]))

    @property
    def loss(self):
        return getattr(self, self.loss_desc.loss_kind + '_loss')

    def get_all_extra_data(self, at_date):
        return self.extra_data or {}

    def get_date(self):
        return self.start_date if hasattr(self, 'start_date') else None

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['claim'] = self.claim
        cur_dict['loss'] = self

    @classmethod
    def validate(cls, instances):
        for instance in instances:
            instance.check_end_date()


class ClaimService(ServiceMixin, model.CoopSQL):
    'Claim Service'
    __name__ = 'claim.service'

    loss = fields.Many2One('claim.loss', 'Loss',
        ondelete='CASCADE', select=True, required=True)
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT',
        required=True)
    extra_datas = fields.One2Many('claim.service.extra_data', 'claim_service',
        'Extra Data', delete_missing=True,
        states={'invisible': ~Eval('extra_datas')},
        depends=['extra_datas'])
    claim = fields.Function(
        fields.Many2One('claim', 'Claim'),
        'get_claim')
    loss_summary = fields.Function(
        fields.Text('Loss Summary'),
        'get_loss_summary')
    benefit_summary = fields.Function(
        fields.Text('Benefit Summary'),
        'get_benefit_summary')

    @classmethod
    def _export_light(cls):
        return super(ClaimService, cls)._export_light() | {'contract',
            'option', 'benefit'}

    def get_claim(self, name):
        if self.loss:
            return self.loss.claim.id

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

        data_values = self.benefit.get_extra_data_def(
            self.extra_datas[-1].extra_data_values, self.loss.get_date())

        self.extra_datas[-1].extra_data_values = data_values

    def get_rec_name(self, name=None):
        if self.benefit:
            res = self.benefit.rec_name
            if self.status:
                res += ' [%s]' % coop_string.translate_value(self, 'status')
            return res
        return super(ClaimService, self).get_rec_name(name)

    def get_benefit_summary(self, name):
        return '%s (%s)' % (self.benefit.rec_name,
            self.option.coverage.insurer.rec_name)

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
        self.on_change_extra_datas()

    def init_from_option(self, option):
        self.option = option
        self.contract = option.parent_contract

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(cur_dict)
        cur_dict['service'] = self
        self.benefit.init_dict_for_rule_engine(cur_dict)
        self.loss.init_dict_for_rule_engine(cur_dict)
        if self.option:
            self.option.init_dict_for_rule_engine(cur_dict)
        elif self.contract:
            self.contract.init_dict_for_rule_engine(cur_dict)

    def get_currency(self):
        if self.option:
            return self.option.get_currency()

    def get_all_extra_data(self, at_date):
        res = {}
        extra_data = utils.get_value_at_date(self.extra_datas, at_date)
        good_extra_data = extra_data.extra_data_values if extra_data else {}
        res.update(good_extra_data)
        res.update(self.loss.get_all_extra_data(at_date))
        if self.option:
            res.update(self.option.get_all_extra_data(at_date))
        elif self.contract:
            res.update(self.contract.get_all_extra_data(at_date))
        return res


class ClaimSubStatus(model.CoopSQL, model.CoopView):
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
        return coop_string.slugify(self.name)

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def get_sub_status(cls, code):
        sub_status_id = cls._get_claim_sub_status_cache.get(code, default=-1)
        if sub_status_id != -1:
            return cls(sub_status_id)
        instance = cls.search([('code', '=', code)])[0]
        cls._get_claim_sub_status_cache.set(code, instance.id)
        return instance


class ClaimServiceExtraDataRevision(model._RevisionMixin, model.CoopSQL,
        model.CoopView, export.ExportImportMixin):
    'Claim Service Extra Data'

    __name__ = 'claim.service.extra_data'
    _parent_name = 'claim_service'
    _func_key = 'date'

    claim_service = fields.Many2One('claim.service', 'Claim Service',
        required=True, select=True, ondelete='CASCADE')
    extra_data_values = fields.Dict('extra_data', 'Extra Data')
    extra_data_values_translated = extra_data_values.translated(
        'extra_data_values')
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary', depends=['extra_data_values']),
        'get_extra_data_summary')

    @staticmethod
    def revision_columns():
        return ['extra_data_values']

    @classmethod
    def get_reverse_field_name(cls):
        return 'extra_data'

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        return Pool().get('extra_data').get_extra_data_summary(extra_datas,
            'extra_data_values')

    @classmethod
    def add_func_key(cls, values):
        if 'date' in values:
            values['_func_key'] = values['date']
        else:
            values['_func_key'] = None
