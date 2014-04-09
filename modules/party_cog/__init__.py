from trytond.pool import Pool
from .party import *
from .category import *
from .contact_mechanism import *
from .address import *
from .test_case import *
from .relationship import *


def register():
    Pool.register(
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
