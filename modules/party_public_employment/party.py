# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval
from trytond.config import config

from trytond.modules.coog_core import fields, model, coog_string


ADMINISTRATIVE_SITUATION = [
    ('active', 'Active'),
    ('retired', 'Retired'),
    ]


__all__ = [
    'AdminSituationSubStatus',
    'EmploymentVersion',
    'PublicEmploymentIndex',
    ]


class EmploymentVersion(metaclass=PoolMeta):
    __name__ = 'party.employment.version'

    administrative_situation = fields.Selection(ADMINISTRATIVE_SITUATION,
        'Administrative Situtation',
        required=True)
    administrative_situation_sub_status = fields.Many2One(
        'party.administrative_situation_sub_status',
        'Administrative Situation Details',
        domain=[('situation', '=', Eval('administrative_situation'))],
        depends=['administrative_situation'],
        ondelete='RESTRICT')
    increased_index = fields.Integer('Increased Index',
        help='Increased public service index used to defined salary',
        domain=['OR', ('increased_index', '=', None),
            ('increased_index', '>', 0)])
    gross_index = fields.Function(
        fields.Integer('Gross Index',
            help='Gross public service index used to defined salary',
            domain=['OR', ('gross_index', '=', None), ('gross_index', '>', 0)]),
        'on_change_with_gross_index', setter='setter_void')
    work_country = fields.Many2One('country.country',
        'Work Country', help='Country where the employee works',
        ondelete='RESTRICT')
    work_subdivision = fields.Many2One('country.subdivision',
        'Subdivision Work Place', help='Subdivision where the employee works',
        domain=[('country', '=', Eval('work_country'))],
        depends=['work_country'], ondelete='RESTRICT')

    @classmethod
    def default_work_country(cls):
        code = config.get('options', 'default_country', default='FR')
        Country = Pool().get('country.country')
        country = Country.search([('code', '=', code)])
        if country:
            return country[0].id

    @fields.depends('increased_index', 'date')
    def on_change_with_gross_index(self, name=None):
        PublicIndex = Pool().get('party.public_employment_index')
        if not self.increased_index:
            return None
        return PublicIndex.get_gross_index_from_increased_index(
            self.increased_index, self.date)

    @fields.depends('gross_index', 'increased_index', 'date')
    def on_change_gross_index(self):
        PublicIndex = Pool().get('party.public_employment_index')
        if self.gross_index:
            self.increased_index = \
                PublicIndex.get_increased_index_from_gross_index(
                    self.gross_index, self.date)

    @fields.depends('gross_index', 'increased_index', 'date')
    def on_change_increased_index(self):
        PublicIndex = Pool().get('party.public_employment_index')
        if self.increased_index:
            self.gross_index = \
                PublicIndex.get_gross_index_from_increased_index(
                    self.increased_index, self.date)


class AdminSituationSubStatus(model.CoogView, model.CoogSQL):
    'Administrative Situation Sub Status'
    __name__ = 'party.administrative_situation_sub_status'
    _func_key = 'name'

    name = fields.Char('Name', required=True,
        help='Name of Administrative Situation Sub Status')
    code = fields.Char('Code', required=True)
    situation = fields.Selection(ADMINISTRATIVE_SITUATION,
        'Administrative Situation',
        help='Define the administration situation (used to filter sub status '
        'according the administrative situation)',
        required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._order = [('code', 'ASC')]
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.code), 'The code must be unique!')
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if not self.code:
            return coog_string.slugify(self.name)
        return self.code


class PublicEmploymentIndex(model.CoogView, model.CoogSQL):
    'Public Employment Index Table'
    __name__ = 'party.public_employment_index'

    effective_date = fields.Date('Effective Date',
        help='Date used to versionned the index')
    gross_index = fields.Integer('Gross Index', required=True)
    increased_index = fields.Integer('Increased Index', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('index_uniq', Unique(t, t.effective_date, t.gross_index),
                'The combination date, gross_index must be unique!'),
            ]

    @classmethod
    def get_gross_index_from_increased_index(cls, increased_index, at_date):
        indexes = cls.search([
                ('effective_date', '<=', at_date),
                ('increased_index', '=', increased_index),
                ], order=[('effective_date', 'DESC')])
        if indexes:
            return indexes[0].gross_index

    @classmethod
    def get_increased_index_from_gross_index(cls, gross_index, at_date):
        indexes = cls.search([
                ('effective_date', '<=', at_date),
                ('gross_index', '=', gross_index),
                ], order=[('effective_date', 'DESC')])
        if indexes:
            return indexes[0].increased_index
