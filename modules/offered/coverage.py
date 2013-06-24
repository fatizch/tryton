#-*- coding:utf-8 -*-
import copy

from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import model, business, fields
from trytond.modules.offered import Offered


__all__ = [
    'Coverage',
    'PackageCoverage',
    'CoverageComplementaryDataRelation',
    ]

SUBSCRIPTION_BEHAVIOUR = [
    ('mandatory', 'Mandatory'),
    ('proposed', 'Proposed'),
    ('optional', 'Optional'),
]


class Coverage(model.CoopSQL, Offered):
    'Coverage'

    __name__ = 'offered.coverage'

    kind = fields.Selection([('', ''), ('default', 'Default')],
        'Coverage Kind')
    products = fields.Many2Many(
        'offered.product-options-coverage',
        'coverage', 'product', 'Products',
        domain=[('currency', '=', Eval('currency'))],
        depends=['currency'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    subscription_behaviour = fields.Selection(SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False)
    is_package = fields.Boolean('Package')
    coverages_in_package = fields.Many2Many('offered.package-coverage',
        'package', 'coverage', 'Coverages In Package',
        states={'invisible': Bool(~Eval('is_package'))},
        depends=['is_package', 'kind'],
        domain=[('is_package', '=', False), ('kind', '=', Eval('kind'))])
    complementary_data_def = fields.Many2Many(
        'offered.coverage-complementary_data_def',
        'coverage', 'complementary_data_def', 'Complementary Data',
        domain=[('kind', 'in', ['contract', 'sub_elem'])])

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        cls.template = copy.copy(cls.template)
        if not cls.template.domain:
            cls.template.domain = []
        cls.template.domain.append(('is_package', '=', Eval('is_package')))
        if not cls.template.depends:
            cls.template = []
        cls.template.depends.append('is_package')

        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True

    def give_me_complementary_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not('options' in dd_args and dd_args['options'] != '' and
                self.code in dd_args['options'].split(';')):
            return [], []
        return self.get_complementary_data_def(
            [dd_args['kind']], args['date']), []

    @staticmethod
    def default_subscription_behaviour():
        return 'mandatory'

    def get_currency(self):
        return self.currency

    @classmethod
    def _export_skips(cls):
        skips = super(Coverage, cls)._export_skips()
        skips.add('products')
        return skips


class PackageCoverage(model.CoopSQL):
    'Link Package Coverage'

    __name__ = 'offered.package-coverage'

    package = fields.Many2One('offered.coverage', 'Package')
    coverage = fields.Many2One('offered.coverage', 'Coverage')


class CoverageComplementaryDataRelation(model.CoopSQL):
    'Relation between Coverage and Complementary Data'

    __name__ = 'offered.coverage-complementary_data_def'

    coverage = fields.Many2One('offered.coverage', 'Coverage',
        ondelete='CASCADE')
    complementary_data_def = fields.Many2One(
        'offered.complementary_data_def',
        'Complementary Data', ondelete='RESTRICT')
