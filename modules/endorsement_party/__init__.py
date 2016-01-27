from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .event import *


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementPart,
        EndorsementPartyField,
        EndorsementAddressField,
        EndorsementRelationField,
        Party,
        Address,
        EndorsementParty,
        EndorsementPartyAddress,
        EndorsementPartyRelation,
        Endorsement,
        ChangePartyBirthDate,
        AddressDisplayer,
        ChangePartyAddress,
        ChangePartySSN,
        PartyNameDisplayer,
        ChangePartyName,
        ChangePartyRelationship,
        RelationDisplayer,
        SelectEndorsement,
        EventTypeAction,
        module='endorsement_party', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_party', type_='wizard')
