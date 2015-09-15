from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *


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
        module='endorsement_party', type_='model')

    Pool.register(
        StartEndorsement,
        module='endorsement_party', type_='wizard')
