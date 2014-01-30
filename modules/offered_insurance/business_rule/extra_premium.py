from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'ExtraPremiumKind',
    ]


class ExtraPremiumKind(model.CoopSQL, model.CoopView):
    'Extra Premium Kind'

    __name__ = 'extra_premium.kind'

    name = fields.Char('Name', on_change=['name'], required=True)
    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super(ExtraPremiumKind, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    def on_change_name(self):
        return {'code': coop_string.remove_invalid_char(self.name)}

    def get_name_for_billing(self):
        return self.name
