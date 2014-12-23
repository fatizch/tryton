from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model, export, coop_string

__all__ = [
    'PlanLines',
    'PlanLinesCoverageRelation',
    'Commission',
    'Plan',
    'PlanRelation',
    'Agent',
    ]
__metaclass__ = PoolMeta


class Commission:
    __name__ = 'commission'
    commissionned_contract = fields.Function(
        fields.Many2One('contract', 'Commissioned Contract'),
        'get_commissionned_contract')
    commissionned_option = fields.Function(
        fields.Many2One('contract.option', 'Commissioned Option'),
        'get_commissionned_option')
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'get_party', searcher='search_party')
    broker = fields.Function(
        fields.Many2One('broker', 'Broker'),
        'get_broker', searcher='search_broker')

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.type_.searcher = 'search_type_'

    def get_commissionned_option(self, name):
        if (self.origin and self.origin.details[0] and
                getattr(self.origin.details[0], 'option', None)):
            return self.origin.details[0].option.id

    def get_commissionned_contract(self, name):
        if (self.origin and self.origin.details[0] and
                getattr(self.origin.details[0], 'option', None)):
            return self.origin.details[0].option.parent_contract.id

    def get_party(self, name):
        return self.agent.party.id if self.agent else None

    def get_broker(self, name):
        return (self.agent.party.broker_role[0].id
            if self.agent and self.agent.party.broker_role else None)

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
        Invoice = pool.get('account.invoice')
        invoices = super(Commission, cls).invoice(commissions)
        in_credit_note_invoice = [invoice for invoice in invoices
            if (invoice.total_amount < 0 and invoice.type == 'in_invoice')]
        out_credit_note_invoice = [invoice for invoice in invoices
            if (invoice.total_amount < 0 and invoice.type == 'out_invoice')]
        if in_credit_note_invoice:
            Invoice.write(in_credit_note_invoice, {'type': 'in_credit_note'})
        if out_credit_note_invoice:
            Invoice.write(in_credit_note_invoice, {'type': 'out_credit_note'})
        return invoices

    @classmethod
    def search_type_(cls, name, clause):
        clause[2] = {'out': 'agent', 'in': 'principal'}.get(clause[2], '')
        return [('agent.type_',) + tuple(clause[1:])],

    @classmethod
    def search_party(cls, name, clause):
        return [('agent.party',) + tuple(clause[1:])],

    @classmethod
    def search_broker(cls, name, clause):
        return [('agent.party.broker_role',) + tuple(clause[1:])],


class Plan(export.ExportImportMixin):
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
        'get_commissionned_products', searcher='search_commissioned_products')
    commissioned_products_name = fields.Function(
        fields.Char('Commissioned Products'),
        'get_commissionned_products_name',
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
        return coop_string.remove_blank_and_invalid_char(self.name)

    def get_commissionned_products(self, name):
        products = []
        for line in self.lines:
            for option in line.options:
                products.extend([product.id for product in option.products])
        return list(set(products))

    def get_commissionned_products_name(self, name):
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
        if 'option' in pattern:
            return pattern['option'] in self.options

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

    from_ = fields.Many2One('commission.plan', 'Plan')
    to = fields.Many2One('commission.plan', 'Plan')


class Agent(export.ExportImportMixin):
    __name__ = 'commission.agent'
    _func_key = 'func_key'

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
