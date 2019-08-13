# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #TEST PARTY EMPLOYMENT ENDORSEMENT
# #Comment# #Imports
import datetime
from proteus import Model, Wizard

from decimal import Decimal

from trytond.tests.tools import activate_modules
from trytond.modules.party_cog.tests.tools import create_party_person

# #Comment# #Install Modules
config = activate_modules('endorsement_party_employment')

# #Comment# #Get Models
ModelsEndorsement = Model.get('endorsement')
EndorsementPartyEmployment = Model.get('endorsement.party.employment')
EndorsementPartyEmploymentVersion = Model.get('endorsement.party.employment.'
    'version')
EndorsementPartyEmploymentField = Model.get('endorsement.party.'
    'employment.field')
EndorsementPartyEmploymentVersionField = Model.get('endorsement.party.'
    'employment.version.field')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get('endorsement.definition'
    '-endorsement.part')
EndorsementPart = Model.get('endorsement.part')
User = Model.get('res.user')
EmploymentVersion = Model.get('party.employment.version')
Employment = Model.get('party.employment')
Party = Model.get('party.party')
EmploymentKind = Model.get('party.employment_kind')
EmploymentWorkTime = Model.get('party.employment_work_time_type')
# #Comment# #Prepare data

endorsement_effective_date = datetime.date(2019, 7, 12)

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)

john = create_party_person()
company = Party(name='cooopengo', is_person=False)
company.save()
employment_kind = EmploymentKind(name='new_kind_job',
    code='new_kind')
employment_kind.save()
employment_work_time = EmploymentWorkTime(name='work_time',
    code='work_time_code')
employment_work_time.save()

date_employment = datetime.date(2019, 1, 1)
first_employment = Employment()
first_employment.employee = john
first_employment.employer = company
first_employment.entry_date = date_employment
first_employment.start_date = date_employment
first_employment.employment_kind = employment_kind
first_employment.save()
first_version = EmploymentVersion()
first_version.employment = first_employment
first_version.work_time_type = employment_work_time
first_version.gross_salary = Decimal(12000)
first_version.date = date_employment
first_version.save()

john, = Party.find(['name', '=', 'Doe'])
definition, = EndorsementDefinition.find(
    ['code', '=', 'party_employment_endorsement'])

# #Comment# #Neither employment nor version is modified

first_endorsement = Wizard('endorsement.start', models=[john])
first_endorsement.form.party = john
first_endorsement.form.endorsement_definition = definition
first_endorsement.form.endorsement = None
first_endorsement.form.applicant = None
first_endorsement.form.effective_date = endorsement_effective_date
first_endorsement.execute('start_endorsement')
first_endorsement.execute('manage_party_employment_next')
first_endorsement.execute('apply_endorsement')

assert (len(john.employments) == 1)
assert ((john.employments[0].employee == john))
assert (john.employments[0].employer == company)
assert (john.employments[0].entry_date == date_employment)
assert (john.employments[0].start_date == date_employment)
assert (john.employments[0].employment_kind == employment_kind)
assert (len(john.employments[0].versions) == 1)
assert (john.employments[0].versions[0].employment == john.employments[0])
assert (john.employments[0].versions[0].work_time_type == employment_work_time)
assert (john.employments[0].versions[0].gross_salary == Decimal(12000))
assert (john.employments[0].versions[0].date == date_employment)

# #Comment# #Modification of the current version 's gross salary

second_endorsement = Wizard('endorsement.start', models=[john])
second_endorsement.form.party = john
second_endorsement.form.endorsement_definition = definition
second_endorsement.form.endorsement = None
second_endorsement.form.applicant = None
second_endorsement.form.effective_date = date_employment
second_endorsement.execute('start_endorsement')

second_endorsement.form.version[0].gross_salary = Decimal(2000)

second_endorsement.execute('manage_party_employment_next')
second_endorsement.execute('apply_endorsement')

assert (len(john.employments[0].versions) == 1)
assert (john.employments[0].versions[0].gross_salary == Decimal(2000))

# #Comment# # Current Version is modified

third_endorsement = Wizard('endorsement.start', models=[john])
third_endorsement.form.party = john
third_endorsement.form.endorsement_definition = definition
third_endorsement.form.endorsement = None
third_endorsement.form.applicant = None
third_endorsement.form.effective_date = endorsement_effective_date
third_endorsement.execute('start_endorsement')
third_endorsement.form.version[0].gross_salary = Decimal(3500)

third_endorsement.execute('manage_party_employment_next')
third_endorsement.execute('apply_endorsement')

assert (len(john.employments[0].versions) == 2)
assert (john.employments[0].versions[1].gross_salary == Decimal(3500))

# #Comment# # Reload the previous object if we go back

forth_endorsement = Wizard('endorsement.start', models=[john])
forth_endorsement.form.party = john
forth_endorsement.form.endorsement_definition = definition
forth_endorsement.form.endorsement = None
forth_endorsement.form.applicant = None
forth_endorsement.form.effective_date = endorsement_effective_date
forth_endorsement.execute('start_endorsement')
forth_endorsement.form.version[0].gross_salary = Decimal(5500)
forth_endorsement.execute('manage_party_employment_next')
forth_endorsement.execute('summary_previous')

assert (forth_endorsement.form.version[0].gross_salary == Decimal(5500))
