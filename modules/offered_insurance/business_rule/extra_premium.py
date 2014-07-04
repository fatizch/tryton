from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'ExtraPremiumKind',
    ]


class ExtraPremiumKind(model.CoopSQL, model.CoopView):
    'Extra Premium Kind'

    __name__ = 'extra_premium.kind'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    is_discount = fields.Boolean('Is Discount')
    max_value = fields.Numeric('Max Value')
    max_rate = fields.Numeric('Max Rate')

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

    def get_name_for_billing(self):
        return self.name
