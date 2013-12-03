from trytond.pool import Pool
from .party import *
from .contact_mechanism import *
from .address import *
from .relation import *
from .test_case import *


def register():
    Pool.register(
        # From party
        Party,
        PartyCategory,
        Actor,
        # From address
        Address,
        AddresseKind,
        # From relation
        PartyRelationKind,
        PartyRelation,
        # From contact_mechanism
        ContactMechanism,
        ContactHistory,
        # from test_case
        TestCaseModel,
        module='coop_party', type_='model')
