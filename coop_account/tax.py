from trytond.model import fields as fields
from trytond.pool import Pool

from trytond.pyson import Eval

from trytond.modules.coop_utils import CoopSQL, CoopView


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
    rates = fields.One2Many(
        'coop_account.tax_version',
        'my_tax_desc',
        'Versionned Rates')

    # To do : CTD0069
    # Check there is no overlapping of versions before save

    def get_good_version_at_date(self, date):
        for rate in self.rates:
            if rate.start_date <= date:
                if hasattr(rate, 'end_date') and rate.end_date:
                    if rate.end_date >= date:
                        return rate
                    continue
                return rate
        return None


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
        [('flat', 'Flat'), ('none', 'None'), ('rate', 'Rate')],
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
        return 'none'

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
            return base * self.rate_value
        elif self.kind == 'flat':
            return self.flat_value
        return 0


class TaxManager(CoopSQL, CoopView):
    '''A class that will manage a set of taxes'''
    __name__ = 'coop_account.tax_manager'

    taxes = fields.Many2Many(
        'coop_account.manager_tax_relation',
        'manager',
        'tax',
        'Taxes')

    def give_appliable_taxes(self, args):
        res = []
        for tax in self.taxes:
            tmp_res = tax.get_good_version_at_date(args['date'])
            if tmp_res:
                res.append(tmp_res)
        return res


class ManagerTaxRelation(CoopSQL):
    '''A Relation between a pricing rule and a tax'''
    __name__ = 'coop_account.manager_tax_relation'
    manager = fields.Many2One(
        'coop_account.tax_manager',
        'Tax Manager',
        ondelete='CASCADE')
    tax = fields.Many2One('coop_account.tax_desc', 'Tax Descriptor')
