# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.coog_core import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'OptionDescriptionTaxRelationForWaiver',
    ]


class OptionDescription:
    __name__ = 'offered.option.description'

    with_waiver_of_premium = fields.Selection([
            ('with_waiver_of_premium', 'With Waiver Of Premium'),
            ('without_waiver_of_premium', 'Without Waiver Of Premium')],
        'With Waiver Of Premium', sort=False)
    taxes_for_waiver = fields.Many2Many('coverage-account.tax-for_waiver',
        'coverage', 'tax', 'Taxes', states={'invisible':
            Eval('with_waiver_of_premium') == 'without_waiver_of_premium'})

    @staticmethod
    def default_with_waiver_of_premium():
        return 'without_waiver_of_premium'

    def get_account_for_waiver_line(self):
        return self.insurer.party.account_payable


class OptionDescriptionTaxRelationForWaiver(model.CoogSQL):
    'Option Description Tax Relation For Waiver'

    __name__ = 'coverage-account.tax-for_waiver'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE', required=True, select=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)
