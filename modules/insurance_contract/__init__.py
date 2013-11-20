from trytond.pool import Pool
from contract import *
from .party import *
from .document import *
from .renewal import *
from .rule_engine import *

from trytond.modules.coop_utils import expand_tree
CoveredElementTreeExpansion = expand_tree('ins_contract.covered_element')
CoveredDataTreeExpansion = expand_tree('ins_contract.covered_data')


def register():
    Pool.register(
        #From Party
        Party,
        Customer,
        # contract.py classes
        InsurancePolicy,
        ContractHistory,
        ManagementRole,
        InsuranceSubscribedCoverage,
        SubscribedCoverageComplement,
        StatusHistory,
        CoveredElement,
        CoveredElementTreeExpansion,
        CoveredElementPartyRelation,
        CoveredData,
        CoveredDataTreeExpansion,
        ContractClause,
        Document,
        DocumentRequest,
        DeliveredService,
        RequestFinder,
        Expense,
        # from renewal
        RenewalStart,
        RenewalResult,
        #From Rule Engine,
        OfferedContext,
        ContractContext,
        module='insurance_contract', type_='model')

    Pool.register(
        RenewalWizard,
        module='insurance_contract', type_='wizard')
