from trytond.pool import Pool
from trytond.modules.coop_utils import export
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

    export.add_export_to_model([
            ('party.category', ()),
            ], 'coop_party')
