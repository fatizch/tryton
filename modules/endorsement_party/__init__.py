# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .endorsement import *
from .offered import *
from .wizard import *
from .event import *
import party


def register():
    Pool.register(
        EndorsementDefinition,
        EndorsementPart,
        EndorsementPartyField,
        EndorsementAddressField,
        EndorsementRelationField,
        Party,
        Relation,
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
        party.PartyReplace,
        module='endorsement_party', type_='wizard')
