# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import Pool
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, If

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.currency_cog import ModelCurrency

FEE_FREQUENCIES = [
    ('', ''),
    ('once_per_contract', 'Once per Contract'),
    ('once_per_invoice', 'Once per Invoice'),
    ('once_per_year', 'Once per Year'),
    ('at_contract_signature', 'At contract signature'),
    ]

__all__ = [
    'Fee',
    ]


class Fee(model.CoogSQL, model.CoogView, ModelCurrency):
    'Fee'

    __name__ = 'account.fee'
    _func_key = 'code'

    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True, ondelete='RESTRICT')
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    frequency = fields.Selection(FEE_FREQUENCIES, 'Frequency', states={
            'invisible': Eval('type', '') != 'fixed',
            'required': Eval('type', '') == 'fixed'})
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ], 'Type', required=True)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'required': Eval('type') == 'fixed',
            'invisible': Eval('type') != 'fixed',
            }, help='In company\'s currency',
        depends=['type', 'currency_digits'])
    rate = fields.Numeric('Rate', digits=(14, 4),
        states={
            'required': Eval('type') == 'percentage',
            'invisible': Eval('type') != 'percentage',
            }, depends=['type'])
    allow_override = fields.Boolean('Allow Override')
    coverages = fields.Many2Many('offered.option.description-account.fee',
        'fee', 'coverage', 'Coverages')

    @classmethod
    def _export_light(cls):
        return super(Fee, cls)._export_light() | {'company'}

    @classmethod
    def _export_skips(cls):
        return super(Fee, cls)._export_skips() | {'coverages'}

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def __setup__(cls):
        super(Fee, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique'),
            ]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency_digits():
        company_id = Transaction().context.get('company', None)
        if not company_id:
            return 2
        return Pool().get('company.company')(company_id).currency.digits

    @staticmethod
    def default_currency_symbol():
        company_id = Transaction().context.get('company', None)
        if not company_id:
            return ''
        return Pool().get('company.company')(company_id).currency.symbol

    @staticmethod
    def default_type():
        return 'fixed'

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def get_currency(self):
        return self.company.currency if self.company else None

    def get_base_premium_dict(self, rated_instance):
        return {
            '_rated_instance': rated_instance,
            '_rated_entity': self,
            }

    def must_be_rated(self, rated_instance, date):
        return (self.frequency == 'at_contract_signature') == (not date)

    def get_base_amount_from_line(self, line):
        # If self only applies on some coverages, filter by coverage
        if self.coverages and line.rated_entity not in self.coverages:
            return 0
        # Do not apply fees on fees
        if line.rated_entity.__name__ == 'account.fee':
            return 0
        return line.amount

    def calculate_amount(self, rule_dict_template):
        contract_fee = rule_dict_template['contract_fee']
        if self.type == 'fixed':
            amount = self.amount
            if self.allow_override:
                amount = contract_fee.overriden_amount
            return amount, self.frequency
        elif self.type == 'percentage':
            base_amount = Decimal(0)
            frequency = ''
            for line in rule_dict_template['_existing_lines']:
                if not frequency and not line.frequency.startswith('once'):
                    frequency = line.frequency
                base_amount += self.get_base_amount_from_line(line)
            rate = self.rate
            if self.allow_override:
                rate = contract_fee.overriden_rate
            # For now, just use some periodic frequency
            return base_amount * rate, frequency

    def do_calculate(self, rule_dict_template):
        PremiumRule = Pool().get('offered.option.description.premium_rule')
        amount, frequency = self.calculate_amount(rule_dict_template)
        if not amount:
            return []
        new_line = PremiumRule._premium_result_class(amount,
            rule_dict_template)
        new_line.frequency = frequency
        new_line.rated_instance = rule_dict_template['contract_fee']
        return [new_line]

    def finalize_lines(self, lines):
        pass

    def calculate_premiums(self, rated_instance, lines):
        rule_dict_template = self.get_base_premium_dict(rated_instance)
        dict_len = len(rule_dict_template)
        all_lines = []
        for date in lines.iterkeys():
            if not self.must_be_rated(rated_instance, date):
                continue
            if len(rule_dict_template) == dict_len:
                rated_instance.init_dict_for_rule_engine(rule_dict_template)
            rule_dict = rule_dict_template.copy()
            rule_dict['date'] = date
            rule_dict['_existing_lines'] = lines[date]
            new_lines = self.do_calculate(rule_dict)
            lines[date] += new_lines
            all_lines += new_lines
        self.finalize_lines(all_lines)
