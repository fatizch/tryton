from trytond.model import fields as fields
from trytond.pool import Pool

from trytond.modules.coop_utils import model as model, utils as utils


__all__ = [
    'FeeDesc',
    'FeeVersion',
    ]


class FeeDesc(model.CoopSQL, model.VersionedObject):
    '''Fee Descriptor'''

    __name__ = 'coop_account.fee_desc'

    name = fields.Char('Fee Name', required=True)
    code = fields.Char('Code', required=True)
    description = fields.Text('Description')
    current_value = fields.Function(fields.Char('Current Value'),
        'get_current_value')

    @classmethod
    def __setup__(cls):
        super(FeeDesc, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

    @classmethod
    def version_model(cls):
        return 'coop_account.fee_version'

    def get_current_value(self, name):
        vers = self.get_version_at_date(utils.today())
        if vers:
            return vers.rec_name
        return ''

    def get_rec_name(self, name):
        res = ''
        if self.code:
            res = self.code
        elif self.name:
            res = self.name
        res += ' (%s)' % self.get_current_value(name)
        return res


class FeeVersion(model.CoopSQL, model.VersionObject):
    '''Fee Version'''

    __name__ = 'coop_account.fee_version'

    kind = fields.Selection(
        [('flat', 'Flat'), ('rate', 'Rate')],
        'Rating mode',
        required=True)
    value = fields.Numeric('Value')

    @classmethod
    def main_model(cls):
        return 'coop_account.fee_desc'

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
