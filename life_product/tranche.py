#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pool import Pool

from trytond.modules.coop_utils.model import CoopSQL, CoopView, utils
from trytond.modules.coop_utils.model import VersionedObject, VersionObject

__all__ = [
    'Tranche',
    'TrancheVersion',
    'TrancheCalculator',
    'TrancheCalculatorLine'
]


class Tranche(CoopSQL, VersionedObject):
    'Tranche'

    __name__ = 'tranche.tranche'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    floor = fields.Function(fields.Numeric('Current Floor'), 'get_floor')
    ceiling = fields.Function(fields.Numeric('Current Ceiling'), 'get_ceiling')

    @classmethod
    def version_model(cls):
        return 'tranche.tranche_version'

    @staticmethod
    def default_versions():
        return utils.create_inst_with_default_val(
            Pool().get('tranche.tranche'), 'versions')

    def get_tranche_value(self, value, at_date=None):
        version = self.get_version_at_date(at_date)
        if not version:
            return 0
        return version.get_tranche_value(value)

    def get_floor(self, name=None, at_date=None):
        version = self.get_version_at_date(at_date)
        if not version:
            return 0
        return version.get_floor(at_date=at_date)

    def get_ceiling(self, name=None, at_date=None):
        version = self.get_version_at_date(at_date)
        if not version:
            return 0
        return version.get_ceiling(at_date=at_date)


class TrancheVersion(CoopSQL, VersionObject):
    'Tranche Version'

    __name__ = 'tranche.tranche_version'

    floor = fields.Many2One('rule_engine', 'Floor', help='Not Included')
    ceiling = fields.Many2One('rule_engine', 'Ceiling',
        help='Included')

    @classmethod
    def main_model(cls):
        return 'tranche.tranche'

    def get_tranche_value(self, value):
        floor = self.get_floor()
        ceiling = self.get_ceiling()
        return (min(value, ceiling) if ceiling else value) - floor

    def get_floor(self, at_date=None):
        args = {}
        if at_date:
            args['date'] = at_date
        return self.floor.compute(args)[0] if self.floor else 0

    def get_ceiling(self, at_date=None):
        args = {}
        if at_date:
            args['date'] = at_date
        return self.ceiling.compute(args)[0] if self.ceiling else None


class TrancheCalculator(CoopSQL, CoopView):
    'Tranche Calculator'

    __name__ = 'tranche.calculator'

    lines = fields.One2Many('tranche.calc_line', 'calculator',
        'Lines')

    def calculate(self, value):
        res = 0
        for line in self.lines:
            res += line.calculate(value)
        return res


class TrancheCalculatorLine(CoopSQL, CoopView):
    'Tranche Calculator Line'

    __name__ = 'tranche.calc_line'

    fixed_value = fields.Numeric('Fixed Amount')
    rate = fields.Numeric('Rate',
        help='Value between 0 and 100')
    contribution_base = fields.Numeric('Contribution Base',
        help='Value between 0 and 100')
    tranche = fields.Many2One('tranche.tranche', 'Tranche', required=True)
    calculator = fields.Many2One('tranche.calculator', 'Calculator')

    def calculate(self, value):
        return (self.fixed_value
            + self.percent_value * self.tranche.get_tranche_value(value))
