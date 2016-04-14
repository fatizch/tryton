import datetime
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.model import ModelView, Unique
from trytond.cache import Cache

from trytond.modules.cog_utils import model, utils, fields
from trytond.modules.cog_utils import coop_string
from trytond.modules.report_engine import Printable
from trytond.modules.contract import ServiceMixin


__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    'Claim',
    'ClaimService',
    ]


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
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @fields.depends('claim')
    def on_change_with_possible_loss_descs(self, name=None):
        res = []
        if not self.claim or not self.claim.main_contract:
            return res
        for benefit in self.claim.main_contract.get_possible_benefits(self):
            res.extend(benefit.loss_descs)
        return [x.id for x in set(res)]

    @fields.depends('loss_desc', 'extra_data')
    def on_change_with_extra_data(self):
        res = {}
        if self.loss_desc:
            res = utils.init_extra_data(
                self.loss_desc.extra_data_def)
        return res

    def get_func_key(self, name):
        return '|'.join([self.claim.name, str(self.get_date()),
                self.loss_desc.loss_kind])

    def get_rec_name(self, name=None):
        return self.claim.rec_name + ' - ' + str(self.get_date()) + ' - ' + (
            self.loss_desc.rec_name if self.loss_desc else '')

    @classmethod
    def get_date_field_for_kind(cls, kind):
        return 'start_date'

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
            Service = Pool().get('claim.service')
            del_service = Service()
            del_service.option = option
            del_service.init_from_loss(self, benefit)
            self.services = self.services + (del_service,)

    def get_claim_sub_status(self):
        return [x.get_claim_sub_status() for x in self.services] or \
            ['instruction']

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
        cur_dict['loss'] = self
        if 'date' not in cur_dict:
            cur_dict['date'] = self.get_date()


class Claim(model.CoopSQL, model.CoopView, Printable):
    'Claim'

    __name__ = 'claim'
    _history = True
    _func_key = 'name'

    name = fields.Char('Number', select=True, states={'readonly': True})
    status = fields.Selection([
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('reopened', 'Reopened'),
            ], 'Status', sort=False, states={'readonly': True})
    status_string = status.translated('status')
    sub_status = fields.Selection([
            ('', ''),
            ('waiting_doc', 'Waiting For Documents'),
            ('instruction', 'Instruction'),
            ('rejected', 'Rejected'),
            ('waiting_validation', 'Waiting Validation'),
            ('validated', 'Validated'),
            ('paid', 'Paid'),
            ], 'Sub Status',
        states={'readonly': True})
    sub_status_string = sub_status.translated('sub_status')
    reopened_reason = fields.Selection([
            ('', ''),
            ('relapse', 'Relapse'),
            ('reclamation', 'Reclamation'),
            ('regularization', 'Regularization')
            ], 'Reopened Reason', sort=False,
        states={'invisible': Eval('status') != 'reopened',
            'required': Eval('status') == 'reopened'})
    declaration_date = fields.Date('Declaration Date', required=True)
    end_date = fields.Date('End Date', states={
            'invisible': Eval('status') != 'closed',
            'readonly': True,
            })
    claimant = fields.Many2One('party.party', 'Claimant', ondelete='RESTRICT',
        required=True, select=True)
    losses = fields.One2Many('claim.loss', 'claim',
        'Losses', states={'readonly': Eval('status') == 'closed'},
        delete_missing=True)
    documents = fields.One2Many('document.request', 'needed_by', 'Documents',
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
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        target_not_required=True)
    _claim_number_generator_cache = Cache('claim_number_generator')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls.__rpc__.update({'get_possible_sub_status': RPC(instantiate=0)})
        cls._error_messages.update({
                'no_main_contract': 'Impossible to find a main contract, '
                'please try again once it has been set',
                })
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.name), 'The number must be unique!'),
            ]
        cls._buttons.update({
                'button_calculate': {
                    'invisible': ~Eval('status').in_(['closed']),
                    }
                })

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for instances, values in zip(actions, actions):
            for claim in instances:
                claim.update_sub_status()
                super(Claim, cls).write([claim],
                    {'sub_status': claim.sub_status})
        super(Claim, cls).write(*args)

    @classmethod
    def _export_light(cls):
        return super(Claim, cls)._export_light() | {'company', 'main_contract',
            'claimant'}

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
            res += ' %s' % self.claimant.get_rec_name('')
        return res

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['name']

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    def is_open(self):
        return self.status in ['open', 'reopened']

    @fields.depends('status')
    def get_possible_sub_status(self):
        if self.status == 'closed':
            return [
                ('', ''),
                ('rejected', 'Rejected'),
                ('paid', 'Paid'),
                ]
        elif self.is_open():
            return [
                ('waiting_doc', 'Waiting For Documents'),
                ('instruction', 'Instruction'),
                ('rejected', 'Rejected'),
                ('waiting_validation', 'Waiting Validation'),
                ('validated', 'Validated'),
                ('paid', 'Paid'),
                ]
        return [('', '')]

    def is_waiting_for_documents(self):
        for doc in getattr(self, 'documents', []):
            if not doc.is_complete:
                return True
        return False

    def get_sub_status(self):
        if self.is_waiting_for_documents():
            return 'waiting_doc'
        sub_statuses = []
        for loss in self.losses:
            sub_statuses.extend(loss.get_claim_sub_status())
        if not sub_statuses:
            return 'instruction'
        if 'waiting_validation' in sub_statuses:
            return 'waiting_validation'
        if 'validated' in sub_statuses:
            return 'validated'
        if 'paid' in sub_statuses:
            return 'paid'
        if 'rejected' in sub_statuses:
            return 'rejected'
        return 'instruction'

    def update_services_extra_data(self):
        for loss in self.losses:
            for service in loss.services:
                service.on_change_extra_data()
                service.save()
        return True

    def update_sub_status(self):
        sub_status = self.get_sub_status()
        if sub_status in [x[0] for x in self.get_possible_sub_status()]:
            self.sub_status = sub_status
        else:
            self.sub_status = ''

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
        """ Assigns a unique name attribute to each item.
        :param items a list of dictionnaries or claim instances
        """
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

    def get_main_loss(self):
        if not self.losses:
            return None
        return self.losses[0]

    def get_main_contract(self):
        loss = self.get_main_loss()
        if not loss or not loss.services:
            return None
        service = loss.services[0]
        return service.option.contract

    def get_sender(self):
        return None

    @staticmethod
    def default_status():
        return 'open'

    @staticmethod
    def default_sub_status():
        return 'instruction'

    def close_claim(self, sub_status=None):
        self.status = 'closed'
        self.end_date = utils.today()
        return True, []

    def reopen_claim(self):
        if self.status == 'closed':
            self.status = 'reopened'
            self.end_date = None
        return True, []

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
        possible_contracts = self.get_possible_contracts()
        return [x.id for x in possible_contracts]

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

    def calculate(self):
        for loss in self.losses:
            for service in loss.services:
                if service.status == 'calculating':
                    service.calculate()
            loss.services = loss.services
        self.losses = self.losses

    @classmethod
    @ModelView.button
    def button_calculate(cls, claims):
        for claim in claims:
            claim.calculate()
        cls.save(claims)


class ClaimService(ServiceMixin, model.CoopSQL):
    'Claim Service'
    __name__ = 'claim.service'

    loss = fields.Many2One('claim.loss', 'Loss',
        ondelete='CASCADE', select=True)
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('extra_data')})
    delivered_amount = fields.Numeric('Delivered Amount', readonly=True,
        states={'invisible': ~Eval('delivered_amount')})

    @classmethod
    def _export_light(cls):
        return super(ClaimService, cls)._export_light() | {'contract',
            'option', 'benefit'}

    @fields.depends('benefit', 'extra_data', 'loss', 'option', 'contract')
    def on_change_extra_data(self):
        args = {'date': self.loss.get_date(), 'level': 'service'}
        self.init_dict_for_rule_engine(args)
        self.extra_data = self.benefit.get_result('calculated_extra_datas',
            args)[0]

    def get_rec_name(self, name=None):
        if self.benefit:
            res = self.benefit.get_rec_name(name)
            if self.status:
                res += ' [%s]' % coop_string.translate_value(self, 'status')
            return res
        return super(ClaimService, self).get_rec_name(name)

    @classmethod
    def add_func_key(cls, values):
        # Update is not handled for now
        values['_func_key'] = None

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        self.func_error = None
        del_amount_dicts, _ = self.benefit.get_result('delivered_amount',
            cur_dict)
        self.delivered_amount = del_amount_dicts[0]['amount_per_unit'].result
        self.status = 'calculated'

    def init_from_loss(self, loss, benefit):
        self.benefit = benefit
        self.on_change_extra_data()

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(cur_dict)
        cur_dict['service'] = self
        self.benefit.init_dict_for_rule_engine(cur_dict)
        self.loss.init_dict_for_rule_engine(cur_dict)
        if self.contract:
            self.contract.init_dict_for_rule_engine(cur_dict)
        if self.option:
            self.option.init_dict_for_rule_engine(cur_dict)

    @classmethod
    def calculate_services(cls, instances):
        for instance in instances:
            res, errs = instance.calculate()

    def get_extra_data_def(self):
        if self.benefit:
            return self.benefit.extra_data_def

    def get_currency(self):
        if self.option:
            return self.option.get_currency()

    def get_all_extra_data(self, at_date):
        res = {}
        if getattr(self, 'extra_data', None):
            res = self.extra_data
        res.update(self.loss.get_all_extra_data(at_date))
        if self.contract:
            res.update(self.contract.get_all_extra_data(at_date))
        if self.option:
            res.update(self.option.get_all_extra_data(at_date))
        return res

    def get_claim_sub_status(self):
        if self.status == 'not_eligible':
            return ['rejected']
        else:
            return ['instruction']
