from trytond.modules.cog_utils import model, fields, coop_string
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'ExtraPremiumKind',
    ]


class ExtraPremiumKind(model.CoopSQL, model.CoopView, ModelCurrency):
    'Extra Premium Kind'
    #TODO : currency is not set, define how
    __name__ = 'extra_premium.kind'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    is_discount = fields.Boolean('Is Discount')
    max_value = fields.Numeric('Max Value')
    max_rate = fields.Numeric('Max Rate')
    max_value_abs = fields.Function(fields.Numeric('Max Value'), 
                        'on_change_with_max_value_abs')
    max_rate_abs = fields.Function(fields.Numeric('Max Rate'), 
                        'on_change_with_max_rate_abs')


    @classmethod
    def __setup__(cls):
        super(ExtraPremiumKind, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @fields.depends('name', 'code')
    def on_change_name(self):
        if self.code:
            return {}
        return {'code': coop_string.remove_blank_and_invalid_char(self.name)}
    
    @fields.depends('is_discount')
    def on_change_is_discount(self):
        changes = {}
        changes['max_value'] = None
        changes['max_rate'] = None
        return changes
    
    @fields.depends('max_value')
    def on_change_with_max_value_abs(self, name=None):
        return abs(self.max_value) if self.max_value else None
    
    @fields.depends('max_rate')
    def on_change_with_max_rate_abs(self, name=None):
        return abs(self.max_rate) if self.max_rate else None
               

    def get_name_for_billing(self):
        return self.name
