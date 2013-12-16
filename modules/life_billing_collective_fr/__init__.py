from trytond.pool import Pool

from .product import *
from .contract import *
from .billing import *
from .rule_engine import *
from .party import *
from .company import *

from trytond.modules.coop_utils import expand_tree
RateLineTreeExpansion = expand_tree('contract.premium_rate.line')
RateNoteLineTreeExpansion = expand_tree('billing.premium_rate.form.line')


def register():
    Pool.register(
        # from Product
        Product,
        Coverage,
        CollectiveRatingRule,
        FareClass,
        FareClassGroup,
        FareClassGroupFareClassRelation,
        SubRatingRule,
        #from Contract
        Contract,
        CoveredData,
        # from billing,
        RateLine,
        RateNote,
        RateNoteLine,
        RateNoteParameters,
        RateNoteParameterClientRelation,
        RateNoteParameterProductRelation,
        RateNoteParameterContractRelation,
        RateNoteParameterGroupPartyRelation,
        RateNotesDisplayer,
        RateNoteSelection,
        RateNoteMoveDisplayer,
        ContractForBilling,
        Move,
        MoveLine,
        # from Rule Engine
        OfferedContext,
        # from Party
        GroupParty,
        Party,
        # For tree expand
        RateLineTreeExpansion,
        RateNoteLineTreeExpansion,
        # from Company
        Company,
        module='life_billing_collective_fr', type_='model')
    Pool.register(
        RateNoteProcess,
        RateNoteReception,
        CollectionWizard,
        module='life_billing_collective_fr', type_='wizard')
