from trytond.modules.cog_utils import model, utils, fields, coop_string


__all__ = [
    'FeeDescription',
    'FeeDescriptionVersion',
    ]


class FeeDescription(model.CoopSQL, model.VersionedObject):
    'Fee Description'

    __name__ = 'account.fee.description'

    name = fields.Char('Fee Name', required=True)
    code = fields.Char('Code', required=True)
    description = fields.Text('Description')

    @classmethod
    def __setup__(cls):
        super(FeeDescription, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @classmethod
    def version_model(cls):
        return 'account.fee.description.version'

    def get_rec_name(self, name):
        return '%s (%s)' % (self.name, self.code)

    def get_name_for_billing(self):
        return self.name

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class FeeDescriptionVersion(model.CoopSQL, model.VersionObject):
    'Fee Description Version'

    __name__ = 'account.fee.description.version'

    kind = fields.Selection([
            ('flat', 'Flat'),
            ('rate', 'Rate')
            ], 'Rating mode', required=True)
    value = fields.Numeric('Value')

    @classmethod
    def main_model(cls):
        return 'account.fee.description'

    @staticmethod
    def default_kind():
        return 'rate'

    @staticmethod
    def default_value():
        return 0

    @staticmethod
    def default_start_date():
        return utils.today()

    def get_code(self):
        return self.my_fee_desc.code

    def apply_fee(self, base):
        if self.kind == 'rate':
            return base * self.value / 100
        elif self.kind == 'flat':
            return self.value
        return 0

    def get_rec_name(self, name):
        res = '%.2f' % self.value
        if self.kind == 'rate':
            res += ' %'
        return res

    def get_value(self):
        if self.kind == 'rate':
            return self.value / 100
        elif self.kind == 'flat':
            return self.value
