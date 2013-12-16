from trytond.modules.coop_utils import model, fields


__all__ = [
    'TaxDesc',
    'TaxVersion',
]


class TaxDesc(model.CoopSQL, model.VersionedObject):
    '''Tax Descriptor'''

    __name__ = 'account.tax.description'

    name = fields.Char('Tax Name')
    code = fields.Char('Code', required=True)
    description = fields.Text('Description')

    @classmethod
    def __setup__(cls):
        super(TaxDesc, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    @classmethod
    def version_model(cls):
        return 'account.tax.description.version'

    def get_rec_name(self, name):
        res = ''
        if self.code:
            res = self.code
        elif self.name:
            res = self.name
        val = self.get_current_rec_name(name)
        if val != '':
            res += ' (%s)' % val
        return res

    def get_name_for_billing(self):
        return self.name


class TaxVersion(model.CoopSQL, model.VersionObject):
    '''Tax Version'''

    __name__ = 'account.tax.description.version'

    kind = fields.Selection(
        [('flat', 'Flat'), ('rate', 'Rate'), ('rule', 'Rule')],
        'Rating mode',
        required=True)
    value = fields.Numeric('Value')

    @classmethod
    def main_model(cls):
        return 'account.tax.description'

    @staticmethod
    def default_kind():
        return 'rate'

    @staticmethod
    def default_value():
        return 0

    def get_code(self):
        return self.my_tax_desc.code

    def apply_tax(self, base):
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
