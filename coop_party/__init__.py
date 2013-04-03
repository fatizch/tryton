from trytond.pool import Pool
from .party import *
from .contact_mechanism import *
from .address import *
from .relation import *


def register():
    Pool.register(
        Party,
        Address,
        Actor,
        PartyRelationKind,
        PartyRelation,
        ContactMechanism,
        GenericActorKind,
        GenericActor,
        AddresseKind,
        ContactHistory,
        module='coop_party', type_='model')
