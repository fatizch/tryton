#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pool import Pool

from trytond.modules.coop_utils.model import CoopSQL, utils
from trytond.modules.coop_utils.model import VersionedObject, VersionObject

__all__ = [
    'Tranche',
    'TrancheVersion',
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

    floor = fields.Many2One('rule_engine', 'Floor', help='Not Included',
        ondelete='RESTRICT')
    ceiling = fields.Many2One('rule_engine', 'Ceiling',
        help='Included', ondelete='RESTRICT')

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
