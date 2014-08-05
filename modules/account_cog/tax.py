from trytond.modules.cog_utils import model, fields, coop_string, export


__all__ = [
    'TaxDescription',
    'TaxDescriptionVersion',
    'Tax',
    'TaxTemplate',
    'TaxCodeTemplate',
    'TaxCode',
    'TaxGroup',
    ]


class TaxDescription(model.CoopSQL, model.VersionedObject):
    'Tax Description'

    __name__ = 'account.tax.description'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True)
    description = fields.Text('Description')

    @classmethod
    def __setup__(cls):
        super(TaxDescription, cls).__setup__()
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

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


class TaxDescriptionVersion(model.CoopSQL, model.VersionObject):
    'Tax Version'

    __name__ = 'account.tax.description.version'

    kind = fields.Selection([
            ('flat', 'Flat'),
            ('rate', 'Rate'),
            ('rule', 'Rule'),
            ], 'Rating mode', required=True)
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


class Tax(export.ExportImportMixin):
    __name__ = 'account.tax'


class TaxTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.template'


class TaxCodeTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.code.template'


class TaxCode(export.ExportImportMixin):
    __name__ = 'account.tax.code'


class TaxGroup(export.ExportImportMixin):
    __name__ = 'account.tax.group'
