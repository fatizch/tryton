from trytond.pool import Pool
from contract import *
from .party import *
from .document import *
from .renewal import *
from .rule_engine import *
from .wizard import *
from .clause import *
from .service import *

from trytond.modules.cog_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('contract.covered_element')
CoveredDataTreeExpansion = expand_tree('contract.covered_data')


def register():
    Pool.register(
        #From Party
        Party,
        # contract.py classes
        Contract,
        ContractAgreementRelation,
        ContractOption,
        CoveredElement,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        CoveredData,
        CoveredDataTreeExpansion,
        DocumentRequestLine,
        DocumentRequest,
        DocumentReceiveRequest,
        # From Service
        ContractService,
        Expense,
        # From Clause
        ContractClause,
        # from renewal
        RenewalStart,
        RenewalResult,
        #From Rule Engine,
        RuleEngineRuntime,
        #From Wizard
        OptionsDisplayer,
        module='insurance_contract', type_='model')

    Pool.register(
        RenewalWizard,
        OptionSubscription,
        module='insurance_contract', type_='wizard')
