from trytond.pool import Pool
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import model, fields, coop_string
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'ExtraPremiumKind',
    ]


class ExtraPremiumKind(model.CoopSQL, model.CoopView, ModelCurrency):
    'Extra Premium Kind'
    __name__ = 'extra_premium.kind'
    _func_key = 'code'

    active = fields.Boolean('Active')
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    is_discount = fields.Boolean('Is Discount')
    max_value = fields.Numeric('Max Value')
    max_rate = fields.Numeric('Max Rate')
    ceiling = fields.Function(fields.Char('Ceiling'),
                        'on_change_with_ceiling')

    @classmethod
    def __setup__(cls):
        super(ExtraPremiumKind, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def view_attributes(cls):
        return super(ExtraPremiumKind, cls).view_attributes() + [
            ('/form/group[@id="flat_amounts"]/'
                'group[@id="flat_amount_discount"]',
                'states', {'invisible': ~Eval('is_discount')}),
            ('/form/group[@id="flat_amounts"]/group[@id="flat_amount"]',
                'states', {'invisible': Bool(Eval('is_discount'))}),
            ('/form/group[@id="rates"]/group[@id="rate_discount"]',
                'states', {'invisible': ~Eval('is_discount')}),
            ('/form/group[@id="rates"]/group[@id="rate"]',
                'states', {'invisible': Bool(Eval('is_discount'))}),
            ('/form/group[@id="invisible"]',
                'states', {'invisible': True}),
            ]

    @staticmethod
    def default_active():
        return True

    def get_currency(self):
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency

    @fields.depends('name', 'code')
    def on_change_name(self):
        if not self.code:
            self.code = coop_string.slugify(self.name)

    @fields.depends('is_discount')
    def on_change_is_discount(self):
        self.max_values = None
        self.max_rate = None

    @fields.depends('max_value', 'max_rate')
    def on_change_with_ceiling(self, name=None):
        ceiling_value, ceiling_rate = '', ''
        if self.max_value:
            ceiling_value = str(abs(self.max_value)) + ' ' + \
                self.currency_symbol
        if self.max_rate:
            ceiling_rate = str(abs(self.max_rate * 100)) + ' %'
        return ceiling_value + ' ' + ceiling_rate
