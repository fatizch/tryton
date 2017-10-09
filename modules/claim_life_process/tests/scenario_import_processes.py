# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Import Processes Scenario
# #Comment# #Imports

from proteus import Model

from trytond.modules.process_cog.tests.tools import test_import_processes
from trytond.tests.tools import activate_modules

# #Comment# #Install Modules
config = activate_modules(['claim_life_process', 'claim_salary_fr',
    'note_authorizations', 'claim_eckert', 'claim_group_process',
    'process_rule', 'claim_eligibility'])
User = Model.get('res.user')
config._context = User.get_preferences(True, config.context)

test_import_processes()
