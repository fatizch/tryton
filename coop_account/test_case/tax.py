from trytond.model import fields as fields
from trytond.pool import Pool

from trytond.modules.coop_utils import CoopSQL, CoopView, utils as utils


__all__ = [
    'TaxDesc',
    'TaxVersion',
    'TaxManager',
    'ManagerTaxRelation']


class TaxDesc(CoopSQL, CoopView):
    '''A Simple Tax Descriptor'''

    __name__ = 'coop_account.tax_desc'

    name = fields.Char('Tax Name')
    code = fields.Char('Code', required=True)
    versions = fields.One2Many(
        'coop_account.tax_version',
        'my_tax_desc',
        'Versionned Rates')
    description = fields.Text('Description')
    current_value = fields.Function(fields.Char('Current Value'),
        'get_current_value')
    # To do : CTD0069
    # Check there is no overlapping of versions before save

    def get_previous_version(self, at_date):
        prev_version = None
        for version in self.versions:
            if version.start_date > at_date:
                return prev_version
            prev_version = version
        return prev_version

    def append_version(self, version):
        rank = 0
        prev_version = self.get_previous_version(version.start_date)
        if prev_version:
            prev_version.end_date = version.start_date - 1
            rank = self.versions.index(prev_version) + 1
        self.versions.insert(rank, version)
        return self

    def get_current_value(self, name):
        vers = utils.get_good_version_at_date(self, 'versions', utils.today())
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


class TaxVersion(CoopSQL, CoopView):
    '''A tax Version'''

    __name__ = 'coop_account.tax_version'

    my_tax_desc = fields.Many2One(
        'coop_account.tax_desc',
        'Tax Descriptor',
        ondelete="CASCADE")
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    kind = fields.Selection(
        [('flat', 'Flat'), ('rate', 'Rate')],
        'Rating mode',
        required=True)
    value = fields.Numeric('Value')

    @staticmethod
    def default_kind():
        return 'rate'

    @staticmethod
    def default_value():
        return 0

    @staticmethod
    def default_start_date():
        date = Pool().get('ir.date').today()
        return date

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


class TaxManager(CoopSQL, CoopView):
    '''A Tax Manager'''
    __name__ = 'coop_account.tax_manager'

    taxes = fields.Many2Many(
        'coop_account.manager_tax_relation',
        'manager',
        'tax',
        'Taxes')

    def give_appliable_taxes(self, args):
        res = []
        for tax in self.taxes:
            res.extend(
                utils.get_good_versions_at_date(tax, 'versions', args['date']))
        return res

    def get_rec_name(self, name):
        taxes = self.give_appliable_taxes({'date': utils.today()})
        return '; '.join([tax.my_tax_desc.rec_name for tax in taxes])


class ManagerTaxRelation(CoopSQL):
    '''A Relation between a pricing rule and a tax'''
    __name__ = 'coop_account.manager_tax_relation'
    manager = fields.Many2One(
        'coop_account.tax_manager',
        'Tax Manager',
        ondelete='CASCADE')
    tax = fields.Many2One('coop_account.tax_desc', 'Tax Descriptor')
