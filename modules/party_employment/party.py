# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import Eval, If, Bool, Not
from trytond.model import Unique

from trytond.modules.coog_core import fields, model, coog_string
from trytond.modules.party_cog.party import STATES_COMPANY

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
    employer = fields.Many2One('party.party', 'Employer', ondelete='RESTRICT',
        domain=[('is_person', '=', False), ('has_role', '=', False)])
    entry_date = fields.Date('Entry Date',
        states={'required': Bool(Eval('employer'))}, depends=['employer'],
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
        'party.work_section', 'Work Section',
        help='Work section where the employee is attached', ondelete='RESTRICT',
        domain=[('legal_entity', '=', Eval('employer'))],
        depends=['employer'])

    @classmethod
    def validate(cls, employments):
        super(Employment, cls).validate(employments)
        for employment in employments:
            employment.check_employment_identifier()

    def check_employment_identifier(self):
        pass

    @classmethod
    def add_func_key(cls, values):
        if ('employer' in values or 'employment_identifier' in values or
                'employment_kind' in values):
            values['_func_key'] = '%s | %s | %s' % (
                values['employer'] if 'employer' in values else '',
                values['employment_identifier']
                if 'employment_identifier' in values else '',
                values['employment_kind']
                if 'employment_kind' in values else '',
                )
        else:
            super().add_func_key(values)

    @fields.depends('employer', 'work_section')
    def on_change_employer(self):
        self.work_section = None

    def get_version_at_date(self, at_date):
        for version in sorted(self.versions,
                key=lambda x: x.date or datetime.date.min, reverse=True):
            if (version.date or datetime.date.min) <= at_date:
                return version

    def get_rec_name(self, name=None):
        return self.employer.rec_name if self.employer else '' \
            + '(' + str(self.start_date) + ')'

    @classmethod
    def fields_modifiable_in_endorsement(cls):
        return ['entry_date', 'start_date', 'end_date', 'employment_kind']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    employments = fields.One2Many('party.employment', 'employee',
        'Employments', delete_missing=True)
    work_section_role = fields.One2Many('party.work_section', 'party',
        'Work Section',
        help='Work section role definition',
        states={'invisible': ~Eval('is_work_section', False) |
            Not(STATES_COMPANY)},
        depends=['is_work_section', 'is_person'])
    is_work_section = fields.Function(
        fields.Boolean('Is Work Section',
            help='If check, the party will be defined as a work section and '
            'can be link to a legal entity',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._role_fields.append('is_work_section')

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
        employments = self.get_employments(at_date)
        for e in employments:
            version = e.get_version_at_date(at_date)
            if version and getattr(version, name, None):
                return getattr(version, name)

    @classmethod
    def non_customer_clause(cls, clause):
        domain = super(Party, cls).non_customer_clause(clause)
        additional_clause = []
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[2]:
            if clause[1] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_work_section', clause[1], False)]
        else:
            if reverse[clause[1]] == '!=' and domain:
                additional_clause += ['OR']
            additional_clause += [('is_work_section', reverse[clause[1]],
                    False)]
        return additional_clause + domain


class EmploymentVersion(model._RevisionMixin, model.CoogView, model.CoogSQL):
    'Employment Version'
    __name__ = 'party.employment.version'
    _parent_name = 'employment'

    employment = fields.Many2One('party.employment', 'Employment',
        select=True, required=True, ondelete='CASCADE')
    work_time_type = fields.Many2One('party.employment_work_time_type',
        'Work Time Type', ondelete='RESTRICT')
    gross_salary = fields.Numeric('Annual Gross Salary')
    annual_salary_premium = fields.Numeric('Annual Salary Premium')

    @classmethod
    def __setup__(cls):
        super(EmploymentVersion, cls).__setup__()
        cls.date.required = True

    @classmethod
    def fields_modifiable_in_endorsement(cls):
        return ['date', 'work_time_type', 'gross_salary',
            'annual_salary_premium']

    @classmethod
    def add_func_key(cls, values):
        if 'date' in values:
            values['_func_key'] = values['date']
        else:
            super().add_func_key(values)


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


class PartyWorkSection(model.CoogSQL, model.CoogView):
    'Party Work Section'
    __name__ = 'party.work_section'
    _func_key = 'func_key'

    party = fields.Many2One('party.party', 'Party',
        help='Work section party record',
        ondelete='RESTRICT', required=True, select=True,
        domain=[('is_person', '=', False)])
    legal_entity = fields.Many2One('party.party', 'Legal Entity',
        help='Legal entity where the work section belongs',
        ondelete='CASCADE', required=True, select=True,
        domain=[('is_person', '=', False)])
    code = fields.Char('Code', required=True)
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identifier_uniq', Unique(t, t.code, t.legal_entity),
             'The code and the legal entity must be unique!')]

    def get_rec_name(self, name):
        return '[%s] %s' % (self.code, self.party.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('code',) + tuple(clause[1:]),
            ('party.name',) + tuple(clause[1:])
            ]

    def get_func_key(self, name):
        return self.code + '|' + self.legal_entity.code

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if not clause[2]:
            return [('id', '=', None)]
        operands = clause[2].split('|')
        if len(operands) == 2:
            section_code, party_code = operands
            return [('code', clause[1], section_code),
                    ('legal_entity.code', clause[1], party_code)]
        else:
            return [('id', '=', None)]
