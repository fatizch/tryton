# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.config import config

from trytond.modules.coog_core import fields, model


ADMINISTRATIVE_SITUATION = [
    ('active', 'Active'),
    ('retired', 'Retired'),
    ]

__all__ = [
    'Party',
    'AdminSituationSubStatus',
    'EmploymentVersion',
    'PublicEmploymentIndex',
    'EmploymentKind',
    'Employment',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    def civil_service_employment_entry_date(self):
        entry_dates = [e.entry_date
            for e in self.get_civil_service_employments()]
        if entry_dates:
            return min(entry_dates)

    def get_civil_service_employments(self):
        return [e for e in self.employments if e.is_civil_service_employment]

    def administrative_situation_at_date(self, date):
        for e in self.get_civil_service_employments():
            if (e.start_date <= date and
                    (not e.end_date or e.end_date >= date)):
                version = e.get_version_at_date(date)
                if version and version.administrative_situation:
                    return version.administrative_situation

    def administrative_situation_sub_status_at_date(self, date):
        for e in self.get_civil_service_employments():
            if (e.start_date <= date and
                    (not e.end_date or e.end_date >= date)):
                version = e.get_version_at_date(date)
                if version and version.administrative_situation_sub_status:
                    return version.administrative_situation_sub_status.code


class Employment(metaclass=PoolMeta):
    __name__ = 'party.employment'

    is_civil_service_employment = fields.Function(
        fields.Boolean('Civil Service Employment',
            depends=['employment_kind']),
        'getter_is_civil_service_employment')
    retirement_pension_identifier = fields.Char('Retirement Pension Identifier',
        states={'invisible': ~(Bool(Eval('is_retired')))
                | ~(Bool(Eval('is_civil_service_employment')))},
        depends=['is_retired', 'is_civil_service_employment'])
    is_retired = fields.Function(
        fields.Boolean('Is retired', depends=['versions']),
        'on_change_with_is_retired')

    @fields.depends('versions')
    def on_change_with_is_retired(self, name=None):
        return any([v.administrative_situation ==
                'retired' for v in self.versions])

    def getter_is_civil_service_employment(self, name):
        return self.employment_kind.is_civil_service_employment \
            if self.employment_kind else None

    @fields.depends('employment_kind', 'is_civil_service_employment')
    def on_change_employment_kind(self):
        if self.employment_kind:
            self.is_civil_service_employment = self.employment_kind. \
                is_civil_service_employment
        else:
            self.is_civil_service_employment = None


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
    def __setup__(cls):
        super(EmploymentVersion, cls).__setup__()
        cls.work_time_type.states['invisible'] = (
            Eval('administrative_situation', '') == 'retired')
        cls.work_time_type.depends.append('administrative_situation')

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

    @classmethod
    def fields_modifiable_in_endorsement(cls):
        return super(EmploymentVersion, cls).fields_modifiable_in_endorsement()\
            + ['administrative_situation',
            'administrative_situation_sub_status', 'increased_index',
            'gross_index', 'work_country', 'work_subdivision']


class AdminSituationSubStatus(model.CodedMixin, model.CoogView):
    'Administrative Situation Sub Status'
    __name__ = 'party.administrative_situation_sub_status'

    situation = fields.Selection(ADMINISTRATIVE_SITUATION,
        'Administrative Situation',
        help='Define the administration situation (used to filter sub status '
        'according the administrative situation)',
        required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('code', 'ASC')]

    @classmethod
    def is_master_object(cls):
        return True


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


class EmploymentKind(metaclass=PoolMeta):
    __name__ = 'party.employment_kind'

    is_civil_service_employment = fields.Boolean('Civil Service Employment',
        help='Is Civil Service Employment')
