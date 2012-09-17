from trytond.model import fields as fields
from trytond.pool import Pool

from trytond.pyson import Eval

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
    code = fields.Char('Code')
    versions = fields.One2Many(
        'coop_account.tax_version',
        'my_tax_desc',
        'Versionned Rates')

    # To do : CTD0069
    # Check there is no overlapping of versions before save


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
    flat_value = fields.Numeric(
        'Flat rate',
        states={'invisible': (Eval('kind') != 'flat')})
    rate_value = fields.Numeric(
        'Appliable Rate',
        states={'invisible': (Eval('kind') != 'rate')})

    @staticmethod
    def default_kind():
        return 'rate'

    @staticmethod
    def default_flat_value():
        return 0

    @staticmethod
    def default_rate_value():
        return 0

    @staticmethod
    def default_start_date():
        date = Pool().get('ir.date').today()
        return date

    def get_code(self):
        return self.my_tax_desc.code

    def apply_tax(self, base):
        if self.kind == 'rate':
            return base * self.rate_value / 100
        elif self.kind == 'flat':
            return self.flat_value
        return 0


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
        return '; '.join([tax.my_tax_desc.name for tax in taxes])


class ManagerTaxRelation(CoopSQL):
    '''A Relation between a pricing rule and a tax'''
    __name__ = 'coop_account.manager_tax_relation'
    manager = fields.Many2One(
        'coop_account.tax_manager',
        'Tax Manager',
        ondelete='CASCADE')
    tax = fields.Many2One('coop_account.tax_desc', 'Tax Descriptor')
