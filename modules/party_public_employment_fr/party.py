# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Not, Bool, If

from trytond.modules.coog_core import model, fields
from trytond.modules.party_cog.party import STATES_COMPANY


__all__ = [
    'Party',
    'Employment',
    'CSRH',
    'PayrollService',
    'PartyWorkSection',
    'PartyWorkSectionSubdivisionRelation',
    'PartySalaryDeductionService',
    ]


class Employment(metaclass=PoolMeta):
    __name__ = 'party.employment'

    payroll_service = fields.Many2One('party.payroll_service',
        'Payroll Service', help='French payroll service for civil service',
        states={'invisible': ~(Bool(Eval('is_civil_service_employment')))},
        depends=['is_civil_service_employment', 'csrh'],
        ondelete='RESTRICT')
    salary_deduction_service = fields.Many2One('party.salary_deduction_service',
        'Salary Deduction Service', help='Service responsible to deduct '
        'insurance premium from salary',
        depends=['is_retired', 'is_civil_service_employment'],
        states={'invisible': Bool(Eval('is_retired'))
                | ~(Bool(Eval('is_civil_service_employment')))},
        ondelete='RESTRICT')
    csrh = fields.Many2One('csrh', 'CSRH',
        depends=['is_retired', 'is_civil_service_employment', 'work_section'],
        states={'invisible': Bool(Eval('is_retired'))
                | ~(Bool(Eval('is_civil_service_employment')))},
        ondelete='RESTRICT')
    payroll_subdivision = fields.Many2One('country.subdivision',
        'Payroll Subdivision',
        depends=['is_retired', 'is_civil_service_employment',
            'possible_subdivision', 'work_section'],
        states={'invisible': Bool(Eval('is_retired'))
                | ~(Bool(Eval('is_civil_service_employment')))},
        domain=[(If(Bool(Eval('work_section', False)),
                [('id', 'in', Eval('possible_subdivision'))],
                []))],
        ondelete='RESTRICT')
    possible_subdivision = fields.Function(
        fields.Many2Many('country.subdivision', None, None,
            'Possible Payroll Subdivision', states={'invisible': True},
            depends=['work_section']),
        'on_change_with_possible_subdivision')
    payroll_care_number = fields.Char('Payroll Care Number', size=2,
        depends=['is_retired', 'is_civil_service_employment'],
        states={'invisible': Bool(Eval('is_retired'))
                | ~(Bool(Eval('is_civil_service_employment')))})
    payroll_assignment_number = fields.Char('Payroll Assignment Number',
        help='Number assign by payroll civil service updated by EDI',
        readonly=True, depends=['is_retired', 'is_civil_service_employment'],
        states={'invisible': Bool(Eval('is_retired'))
                | ~(Bool(Eval('is_civil_service_employment')))})

    @fields.depends('payroll_service', 'csrh')
    def on_change_csrh(self, name=None):
        if self.csrh and self.csrh.payroll_service:
            self.payroll_service = self.csrh.payroll_service

    @fields.depends('work_section', 'csrh', 'payroll_service',
        'possible_subdivision', 'payroll_subdivision')
    def on_change_work_section(self, name=None):
        if not self.work_section:
            return
        if self.work_section.csrh:
            self.csrh = self.work_section.csrh
            if self.csrh.payroll_service:
                self.payroll_service = self.csrh.payroll_service
        if len(self.work_section.attached_subdivision) == 1:
            self.payroll_subdivision = self.work_section.attached_subdivision[0]

    @fields.depends('work_section')
    def on_change_with_possible_subdivision(self, name=None):
        if self.work_section:
            return [x.id for x in self.work_section.attached_subdivision]

    def check_employment_identifier(self):
        if self.is_civil_service_employment:
            if not self.check_civil_service_identifier():
                raise ValidationError(gettext(
                        'party_public_employment_fr'
                        '.msg_invalid_employment_identifier'))

    def check_civil_service_identifier(self):
        if not self.employment_identifier:
            return True
        pattern = "^[0-9]{15}$"
        return re.search(pattern,
            self.employment_identifier, re.X)

    def check_payroll_care_number(self):
        if not self.payroll_care_number:
            return
        pattern = "^[0-9]*$"
        if not re.search(pattern, self.payroll_care_number, re.X):
            raise ValidationError(gettext('party_public_employment_fr'
                    '.msg_payroll_care_number'))

    @classmethod
    def validate(cls, employments):
        super(Employment, cls).validate(employments)
        for employment in employments:
            employment.check_payroll_care_number()


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    csrh_role = fields.One2Many('csrh', 'party', 'CSRH',
        help='French Human Ressources for Public Service',
        states={'invisible': ~Eval('is_csrh', False) | Not(STATES_COMPANY)},
        depends=['is_csrh', 'is_person'])
    is_csrh = fields.Function(
        fields.Boolean('Is CSRH',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')
    payroll_service_role = fields.One2Many('party.payroll_service', 'party',
        'Payroll Service', help='French Payroll Service for Public Service',
        states={'invisible': ~Eval('is_payroll_service', False) |
            Not(STATES_COMPANY)},
        depends=['is_payroll_service', 'is_person'])
    is_payroll_service = fields.Function(
        fields.Boolean('Is Payroll Service',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._role_fields.append('is_csrh')
        cls._role_fields.append('is_payroll_service')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('/form/notebook/page[@id="role"]/notebook/page[@id="csrh"]',
                'states', {'invisible': Bool(~Eval('is_csrh'))}),
            ('/form/notebook/page[@id="role"]/notebook/page[@'
                'id="payroll_service"]',
                'states', {'invisible': Bool(~Eval('is_payroll_service'))}),
            ]

    @classmethod
    def non_customer_clause(cls, clause):
        domain = super(Party, cls).non_customer_clause(clause)
        additional_clause = []
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[2]:
            additional_clause = [[('is_csrh', clause[1], False)],
                    [('is_payroll_service', clause[1], False)]]
            if clause[1] == '!=' and domain:
                additional_clause = ['OR'] + [['OR'], additional_clause]
        else:
            additional_clause = [[('is_csrh', reverse[clause[1]], False)],
                    [('is_payroll_service', reverse[clause[1]], False)]]
            if clause[1] == '!=' and domain:
                additional_clause = ['OR'] + [['OR'], additional_clause]
        return additional_clause + domain

    def get_rec_name(self, name):
        if self.is_csrh or self.is_payroll_service:
            return self.name
        else:
            return super(Party, self).get_rec_name(name)


class CSRH(model.CoogView, model.CoogSQL):
    'CSRH'
    __name__ = 'csrh'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True,
        help='The string that will be used to identify this record across the '
        'configuration. It should not be modified without checking first if '
        'it is used somewhere')
    party = fields.Many2One('party.party', 'CSRH', ondelete='RESTRICT',
        required=True, domain=[('is_person', '=', False)])
    payroll_service = fields.Many2One('party.payroll_service',
        'Payroll Service', ondelete='RESTRICT')

    @classmethod
    def is_master_object(cls):
        return True

    def get_rec_name(self, name):
        return (self.party.rec_name
            if self.party else super(CSRH, self).get_rec_name(name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]


class PayrollService(model.CoogView, model.CoogSQL):
    'Payroll Service'
    __name__ = 'party.payroll_service'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True,
        help='The string that will be used to identify this record across the '
        'configuration. It should not be modified without checking first if '
        'it is used somewhere')
    party = fields.Many2One('party.party', 'Payroll Service',
        ondelete='RESTRICT', required=True, domain=[('is_person', '=', False)])

    @classmethod
    def is_master_object(cls):
        return True

    def get_rec_name(self, name):
        return (self.party.rec_name
            if self.party else super(PayrollService, self).get_rec_name(name))

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]


class PartyWorkSection(metaclass=PoolMeta):
    __name__ = 'party.work_section'

    attached_subdivision = fields.Many2Many(
        'party.work_section-country.subdivision',
        'work_section', 'subdivision', 'Subdivisions')
    csrh = fields.Many2One('csrh', 'CSRH',
        help='CSRH used by this work section',
        ondelete='RESTRICT')


class PartyWorkSectionSubdivisionRelation(model.CoogSQL):
    'Party Work Section Subdivision Relation'
    __name__ = 'party.work_section-country.subdivision'

    work_section = fields.Many2One(
        'party.work_section',
        'Work Section', required=True, ondelete='CASCADE')
    subdivision = fields.Many2One(
        'country.subdivision',
        'Subdivision', required=True, ondelete='RESTRICT')


class PartySalaryDeductionService(model.CodedMixin, model.CoogView):
    'Party Salary Deduction Service'

    __name__ = 'party.salary_deduction_service'
    _func_key = 'code'
