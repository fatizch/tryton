from trytond.pool import Pool

from .product import *
from .contract import *
from .billing import *
from .rule_engine import *
from .party import *


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
        # from Rule Engine
        OfferedContext,
        # From Party
        GroupParty,
        Party,
        module='life_billing_collective_fr', type_='model')
    Pool.register(
        RateNoteProcess,
        module='life_billing_collective_fr', type_='wizard')
