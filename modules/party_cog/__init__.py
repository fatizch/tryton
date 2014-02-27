from trytond.pool import Pool
from .party import *
from .category import *
from .contact_mechanism import *
from .address import *
from .relation import *
from .test_case import *


def register():
    Pool.register(
        # From party
        Party,
        # From category
        PartyCategory,
        # From address
        Address,
        # From relation
        PartyRelationKind,
        PartyRelation,
        # From contact_mechanism
        ContactMechanism,
        PartyInteraction,
        # from test_case
        TestCaseModel,
        module='party_cog', type_='model')
