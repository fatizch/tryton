from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.wizard import StateAction

from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.cog_utils import fields, model, export, coop_string, utils

__all__ = [
    'PlanLines',
    'PlanLinesCoverageRelation',
    'Commission',
    'Plan',
    'PlanRelation',
    'Agent',
    'CreateAgents',
    'CreateAgentsParties',
    'CreateAgentsAsk',
    'CreateInvoice',
    'CreateInvoiceAsk',
    ]
__metaclass__ = PoolMeta


class Commission:
    __name__ = 'commission'
    commissioned_contract = fields.Function(
        fields.Many2One('contract', 'Commissioned Contract'),
        'get_commissioned_contract')
    commissioned_option = fields.Function(
        fields.Many2One('contract.option', 'Commissioned Option'),
        'get_commissioned_option')
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'get_party', searcher='search_party')
    broker = fields.Function(
        fields.Many2One('distribution.network', 'Broker'),
        'get_broker', searcher='search_broker')
    commission_rate = fields.Numeric('Commission Rate')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.invoice_line.select = True
        cls.type_.searcher = 'search_type_'

    def get_commissioned_option(self, name):
        if self.origin and self.origin.details[0]:
            option = self.origin.details[0].get_option()
            if option:
                return option.id

    def get_commissioned_contract(self, name):
        if self.origin and self.origin.details[0]:
            option = self.origin.details[0].get_option()
            if option:
                return option.parent_contract.id

    def get_party(self, name):
        return self.agent.party.id if self.agent else None

    def get_broker(self, name):
        return (self.agent.party.network[0].id
            if self.agent and self.agent.party.network else None)

    def _group_to_invoice_key(self):
        direction = {
            'in': 'out',
            'out': 'in',
            }.get(self.type_)
        document = 'invoice'
        return (('agent', self.agent),
            ('type', '%s_%s' % (direction, document)),
            )

    @classmethod
    def invoice(cls, commissions):
        pool = Pool()
        Fee = pool.get('account.fee')
        super(Commission, cls).invoice(commissions)
        invoices = list(set([c.invoice_line.invoice for c in commissions]))
        Fee.add_broker_fees_to_invoice(invoices)

    @classmethod
    def search_type_(cls, name, clause):
        clause[2] = {'out': 'agent', 'in': 'principal'}.get(clause[2], '')
        return [('agent.type_',) + tuple(clause[1:])],

    @classmethod
    def search_party(cls, name, clause):
        return [('agent.party',) + tuple(clause[1:])],

    @classmethod
    def search_broker(cls, name, clause):
        return [('agent.party.network',) + tuple(clause[1:])],


class Plan(export.ExportImportMixin, model.TaggedMixin):
    __name__ = 'commission.plan'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    type_ = fields.Selection([
            ('agent', 'Broker'),
            ('principal', 'Insurer'),
            ], 'Type', required=True)
    insurer_plan = fields.One2One('commission_plan-commission_plan',
        'from_', 'to', 'Insurer Plan',
        states={'invisible': Eval('type_') != 'agent'},
        domain=[('type_', '=', 'principal')],
        depends=['type_'])
    broker_plan = fields.One2One('commission_plan-commission_plan',
        'to', 'from_', 'Broker Plan',
        states={'invisible': Eval('type_') != 'principal'},
        domain=[('type_', '=', 'agent')],
        depends=['type_'])
    commissioned_products = fields.Function(
        fields.Many2Many('offered.product', None, None,
            'Commissioned Products'),
        'get_commissioned_products', searcher='search_commissioned_products')
    commissioned_products_name = fields.Function(
        fields.Char('Commissioned Products'),
        'get_commissioned_products_name',
        searcher='search_commissioned_products')

    @classmethod
    def __setup__(cls):
        super(Plan, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @classmethod
    def _export_skips(cls):
        return super(Plan, cls)._export_skips() | {'broker_plan'}

    @classmethod
    def _export_light(cls):
        return super(Plan, cls)._export_light() | {'commission_product'}

    @classmethod
    def copy(cls, commissions, default=None):
        if default is None:
            default = {}
        default.setdefault('code', 'temp_for_copy')
        clones = super(Plan, cls).copy(commissions, default=default)
        for clone, original in zip(clones, commissions):
            clone.code = original.code + '_1'
            clone.save()
        return clones

    @staticmethod
    def default_type_():
        return 'agent'

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product)
        context['names']['nb_years'] = (pattern or {}).get('nb_years', 0)
        context['names']['invoice_line'] = (pattern or {}).get('invoice_line',
            None)
        return context

    def compute(self, amount, product, pattern=None):
        'Compute commission amount for the amount'
        if pattern is None:
            pattern = {}
        pattern['product'] = product.id if product else None
        context = self.get_context_formula(amount, product, pattern)
        for line in self.lines:
            if line.match(pattern):
                return line.get_amount(**context)

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def get_commissioned_products(self, name):
        products = []
        for line in self.lines:
            for option in line.options:
                products.extend([product.id for product in option.products])
        return list(set(products))

    def get_commissioned_products_name(self, name):
        return ', '.join([x.name for x in self.commissioned_products])

    @classmethod
    def search_commissioned_products(cls, name, clause):
        return [('lines.options.products',) + tuple(clause[1:])]


class PlanLines(export.ExportImportMixin):
    __name__ = 'commission.plan.line'

    options = fields.Many2Many(
        'commission.plan.lines-offered.option.description', 'plan_line',
        'option', 'Options')
    options_extract = fields.Function(fields.Text('Options'),
        'get_options_extract')

    def match(self, pattern):
        if 'coverage' in pattern:
            return pattern['coverage'] in self.options

    def get_options_extract(self, name):
        return ' \n'.join((option.name for option in self.options))

    @classmethod
    def _export_light(cls):
        return (super(PlanLines, cls)._export_light() | set(['options']))


class PlanLinesCoverageRelation(model.CoopSQL, model.CoopView):
    'Commission Plan Line - Offered Option Description'
    __name__ = 'commission.plan.lines-offered.option.description'

    plan_line = fields.Many2One('commission.plan.line', 'Plan Line',
        ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class PlanRelation(model.CoopSQL, model.CoopView):
    'Commission Plan - Commission Plan'
    __name__ = 'commission_plan-commission_plan'

    from_ = fields.Many2One('commission.plan', 'Plan', ondelete='CASCADE')
    to = fields.Many2One('commission.plan', 'Plan', ondelete='RESTRICT')


class Agent(export.ExportImportMixin):
    __name__ = 'commission.agent'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Agent, cls).__setup__()
        cls.plan.domain = [('type_', '=', Eval('type_'))]
        cls.plan.depends = ['type_']
        cls.plan.required = True

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return (super(Agent, cls)._export_light() |
            set(['company', 'currency', 'plan']))

    def get_func_key(self, name):
        return '%s|%s' % ((self.party.code, self.plan.code))

    def get_rec_name(self, name):
        return self.plan.rec_name

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                party_code, plan_code = clause[2].split('|')
                return [('party.code', clause[1], party_code),
                    ('plan.code', clause[1], plan_code)]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('party.code',) + tuple(clause[1:])],
                [('plan.code',) + tuple(clause[1:])],
                ]


class CreateAgents(Wizard):
    'Create Agents'

    __name__ = 'commission.create_agents'

    start_state = 'parties'
    parties = StateView('commission.create_agents.parties',
        'commission_insurance.commission_create_agents_parties_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'create_brokers', 'tryton-go-next',
                default=True),
            ])
    create_brokers = StateTransition()
    ask = StateView('commission.create_agents.ask',
        'commission_insurance.commission_create_agents_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('commission.act_agent_form')

    def transition_create_brokers(self):
        pool = Pool()
        Party = pool.get('party.party')
        PaymentTerm = pool.get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search([])
        if self.parties.parties:
            Party.write(list(self.parties.parties), {
                    'account_payable': self.parties.account_payable.id,
                    'supplier_payment_term': payment_terms[0].id,
                    })

        Network = pool.get('distribution.network')
        networks = []
        Address = pool.get('party.address')
        adresses_to_create = []
        adresses_to_write = []
        for party in self.parties.parties:
            address = party.address_get('invoice')
            if not address:
                adresses_to_create.append({'party': party.id, 'invoice': True})
            elif not address.invoice:
                adresses_to_write.append(address)
            if party.network:
                continue
            networks.append({'party': party.id})

        if networks:
            Network.create(networks)
        if adresses_to_create:
            Address.create(adresses_to_create)
        if adresses_to_write:
            Address.write(adresses_to_write, {'invoice': True})
        return 'ask'

    def new_agent(self, party, plan):
        return {
            'party': party.id,
            'plan': plan.id,
            'company': self.parties.company.id,
            'currency': self.parties.company.currency.id,
            'type_': 'agent',
            }

    def agent_update_values(self):
        return {}

    def do_create_(self, action):
        pool = Pool()
        Agent = pool.get('commission.agent')
        existing_agents = {}
        agents_to_create = []
        agents_to_update = []
        agents = []
        for party_slice in grouped_slice([x.party for x in self.ask.brokers]):
            for agent in Agent.search([
                    ('party', 'in', [x.id for x in party_slice]),
                    ('plan', 'in', [x.id for x in self.ask.plans]),
                    ('company', '=', self.parties.company),
                    ('currency', '=', self.parties.company.currency),
                    ('type_', '=', 'agent'),
                    ]):
                existing_agents[(agent.party.id, agent.plan.id)] = agent
        for party in [x.party for x in self.ask.brokers]:
            for plan in self.ask.plans:
                agent = existing_agents.get((party.id, plan.id), None)
                if agent:
                    agents_to_update.append(agent)
                else:
                    agents_to_create.append(self.new_agent(party, plan))
        if agents_to_create:
            agents += [x.id for x in Agent.create(agents_to_create)]

        vals = self.agent_update_values()
        if vals and agents_to_update:
            Agent.write(agents_to_update, vals)
            agents += [x.id for x in agents_to_update]
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode([('id', 'in', agents)])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    def default_ask(self, name):
        return {
            'brokers': [x.network[0].id for x in self.parties.parties],
            }


class CreateAgentsParties(model.CoopView):
    'Create Agents'

    __name__ = 'commission.create_agents.parties'

    company = fields.Many2One('company.company', 'Company', required=True)
    parties = fields.Many2Many('party.party', None, None, 'Parties',
        domain=[
            ('is_company', '=', True),
            ('is_bank', '=', False),
            ('is_insurer', '=', False),
            ])
    account_payable = fields.Many2One('account.account', 'Account Payable',
        domain=[
            ('kind', '=', 'payable'),
            ('company', '=', Eval('company')),
            ],
        states={'required': Bool(Eval('parties'))},
        depends=['company', 'parties'])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateAgentsAsk(model.CoopView):
    'Create Agents'

    __name__ = 'commission.create_agents.ask'

    company = fields.Many2One('company.company', 'Company', required=True)
    brokers = fields.Many2Many('distribution.network', None, None, 'Brokers',
        domain=[('party', '!=', None)], required=True)
    plans = fields.Many2Many('commission.plan', None, None, 'Plans',
        domain=[('type_', '=', 'agent')], required=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateInvoice:
    __name__ = 'commission.create_invoice'

    def do_create_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Commission = pool.get('commission')
        commissions = Commission.search(self.get_domain(),
            order=[('agent', 'DESC'), ('date', 'DESC')])
        Commission.invoice(commissions)
        invoices = list(set([c.invoice_line.invoice for c in commissions]))
        if self.ask.post_invoices:
            Invoice.write(invoices, {'invoice_date': utils.today()})
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [i.id for i in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class CreateInvoiceAsk:
    __name__ = 'commission.create_invoice.ask'

    post_invoices = fields.Boolean('Post Invoices')

    @classmethod
    def __setup__(cls):
        cls.type_.states = {'invisible': True}
        super(CreateInvoiceAsk, cls).__setup__()

    @staticmethod
    def default_type_():
        return 'out'
