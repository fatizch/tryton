from trytond.pool import Pool

from .product import *
from .contract import *
from .billing import *
from .rule_engine import *
from .party import *

from trytond.modules.coop_utils import expand_tree
RateLineTreeExpansion = expand_tree('billing.rate_line')
RateNoteLineTreeExpansion = expand_tree('billing.rate_note_line')


def register():
    Pool.register(
        # From Product
        Product,
        Coverage,
        CollectiveRatingRule,
        FareClass,
        FareClassGroup,
        FareClassGroupFareClassRelation,
        SubRatingRule,
        #From Contract
        Contract,
        CoveredData,
        # From billing,
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
        SuspenseParty,
        Configuration,
        Move,
        MoveLine,
        # from Rule Engine
        OfferedContext,
        # From Party
        GroupParty,
        Party,
        #For tree expand
        RateLineTreeExpansion,
        RateNoteLineTreeExpansion,
        module='life_billing_collective_fr', type_='model')
    Pool.register(
        RateNoteProcess,
        RateNoteReception,
        module='life_billing_collective_fr', type_='wizard')
