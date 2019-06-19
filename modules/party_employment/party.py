# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields, model, coog_string
from trytond.pyson import Eval, If, Bool
from trytond.model import Unique

__all__ = [
    'Employment',
    'Party',
    'EmploymentVersion',
    'EmploymentKind',
    'EmploymentWorkTimeType',
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


class EmploymentVersion(model._RevisionMixin, model.CoogView, model.CoogSQL):
    'Employment Version'
    __name__ = 'party.employment.version'

    employment = fields.Many2One('party.employment', 'Employment',
        select=True, required=True, ondelete='RESTRICT')
    work_time_type = fields.Many2One('party.employment_work_time_type',
        'Work Time Type', ondelete='RESTRICT')
    gross_salary = fields.Numeric('Gross Salary')

    @classmethod
    def __setup__(cls):
        super(EmploymentVersion, cls).__setup__()
        cls.date.required = True


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
