from trytond.pool import Pool
from .party import *
from .contact_mechanism import *
from .relation import *


def register():
    Pool.register(
        Party,
        Company,
        Employee,
        Actor,
        Person,
        PartyRelationKind,
        PartyRelation,
        ContactMechanism,
        GenericActorKind,
        GenericActor,
        module='coop_party', type_='model')
