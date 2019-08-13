# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.model import Unique

from trytond.modules.coog_core import fields, model, coog_string

__all__ = [
    'Employment',
    'Party',
    'EmploymentVersion',
    'EmploymentKind',
    'EmploymentWorkTimeType',
    'PartyWorkSection',
    ]


class Employment(model.CoogSQL, model.CoogView):
    'Employment'
    __name__ = 'party.employment'

    employee = fields.Many2One('party.party', 'Employee',
        required=True, ondelete='RESTRICT', domain=[('is_person', '=', True)])
    employer = fields.Many2One('party.party', 'Employer',
        required=True, ondelete='RESTRICT',
        domain=[('is_person', '=', False), ('has_role', '=', False)])
    entry_date = fields.Date('Entry Date', required=True,
        help='Date of entry in the legal entity')
    start_date = fields.Date('Start Date', required=True,
        help='Begin date of the employment contract')
    end_date = fields.Date('End Date',
        domain=[(If(Bool(Eval('end_date', False)),
            [('end_date', '>=', Eval('start_date'))], []))],
        depends=['start_date'],
        help='End date of the employment contract')
    employment_kind = fields.Many2One('party.employment_kind',
        'Employment Kind', ondelete='RESTRICT', required=True)
    versions = fields.One2Many('party.employment.version',
        'employment', 'Versions', delete_missing=True)
    employment_identifier = fields.Char('Employment Identifier',
        help='The identifier of the employee in his company')
    work_section = fields.Many2One(
        'party.work_section', 'Work Section', ondelete='RESTRICT',
        domain=[('party', '=', Eval('employer'))],
        depends=['employer'])

    @classmethod
    def validate(cls, employments):
        super(Employment, cls).validate(employments)
        for employment in employments:
            employment.check_employment_identifier()

    def check_employment_identifier(self):
        pass

    @fields.depends('employer', 'work_section')
    def on_change_employer(self):
        self.work_section = None

    def get_rec_name(self, name=None):
        return self.employer.rec_name + '(' + str(self.start_date) + ')'

    @classmethod
    def fields_modifiable_in_endorsement(cls):
        return ['entry_date', 'start_date', 'end_date', 'employment_kind']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    employments = fields.One2Many('party.employment', 'employee',
        'Employments', delete_missing=True)

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ("/form/notebook/page[@id='employment']", 'states',
                 {'invisible': ~Eval('is_person')}),
            ]

    def get_employments(self, at_date):
        return [e for e in self.employments
            if e.start_date <= at_date and
            (e.end_date or datetime.date.max) >= at_date]

    def get_employment_version_data(self, name, at_date):
        if not self.is_person:
            return
        Version = Pool().get('party.employment.version')
        employments = self.get_employments(at_date)
        for e in employments:
            version = Version.version_at_date(e, at_date)
            if getattr(version, name, None):
                return getattr(version, name)


class EmploymentVersion(model._RevisionMixin, model.CoogView, model.CoogSQL):
    'Employment Version'
    __name__ = 'party.employment.version'
    _parent_name = 'employment'

    employment = fields.Many2One('party.employment', 'Employment',
        select=True, required=True, ondelete='RESTRICT')
    work_time_type = fields.Many2One('party.employment_work_time_type',
        'Work Time Type', ondelete='RESTRICT')
    gross_salary = fields.Numeric('Annual Gross Salary')

    @classmethod
    def __setup__(cls):
        super(EmploymentVersion, cls).__setup__()
        cls.date.required = True

    @classmethod
    def fields_modifiable_in_endorsement(cls):
        return ['work_time_type', 'gross_salary', 'date']


class EmploymentKind(model.CoogSQL, model.CoogView):
    'Employment Kind'
    __name__ = 'party.employment_kind'
    _func_key = 'code'

    name = fields.Char('Name', required=True, help='Employment kind name')
    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.code),
             'The code must be unique!')
            ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if not self.code:
            return coog_string.slugify(self.name)
        return self.code


class EmploymentWorkTimeType(model.CoogView, model.CoogSQL):
    'Employment Work Time Type'
    __name__ = 'party.employment_work_time_type'
    _func_key = 'code'

    name = fields.Char('Name', required=True,
        help='Employment work time type name')
    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.code),
             'The code must be unique!'),
        ]

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if not self.code:
            return coog_string.slugify(self.name)
        return self.code


class PartyWorkSection(model.CoogView, model.CoogSQL):
    'Party Work Section'
    __name__ = 'party.work_section'

    party = fields.Many2One('party.party', 'Party',
        ondelete='RESTRICT', required=True, domain=[('is_person', '=', False)])
    name = fields.Char('Name', required=True, help='Work Section Name')
    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.code, t.party),
             'The code and the party must be unique!')]
