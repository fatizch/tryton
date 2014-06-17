from trytond.pool import Pool
from .party import *
from .category import *
from .contact_mechanism import *
from .address import *
from .test_case import *
from .relationship import *
from .res import *

from trytond.modules.cog_utils import expand_tree
PartyMenuTreeExpansion = expand_tree('party.synthesis.menu')


def register():
    Pool.register(
        User,
        SynthesisMenuActionCloseSynthesis,
        SynthesisMenuActionRefreshSynthesis,
        SynthesisMenuContact,
        SynthesisMenuAddress,
        SynthesisMenuPartyInteraction,
        SynthesisMenuRelationship,
        SynthesisMenu,
        SynthesisMenuOpenState,
        PartyMenuTreeExpansion,
        Party,
        PartyCategory,
        Address,
        ContactMechanism,
        PartyInteraction,
        TestCaseModel,
        RelationType,
        PartyRelation,
        PartyRelationAll,
        module='party_cog', type_='model')
    Pool.register(
        SynthesisMenuSet,
        SynthesisMenuOpen,
        module='party_cog', type_='wizard')
