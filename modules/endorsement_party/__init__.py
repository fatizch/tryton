# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import endorsement
from . import offered
from . import wizard
from . import event
from . import party
from . import api


def register():
    Pool.register(
        offered.EndorsementDefinition,
        offered.EndorsementPart,
        offered.EndorsementPartyField,
        offered.EndorsementAddressField,
        offered.EndorsementRelationField,
        endorsement.Party,
        endorsement.Relation,
        endorsement.Address,
        endorsement.EndorsementParty,
        endorsement.EndorsementPartyAddress,
        endorsement.EndorsementPartyRelation,
        endorsement.Endorsement,
        wizard.ChangePartyBirthDate,
        wizard.AddressDisplayer,
        wizard.ChangePartyAddress,
        wizard.PartyNameDisplayer,
        wizard.ChangePartyName,
        wizard.ChangePartyRelationship,
        wizard.RelationDisplayer,
        wizard.SelectEndorsement,
        event.EventTypeAction,
        module='endorsement_party', type_='model')
    Pool.register(
        wizard.ChangePartySSN,
        depends=['party_ssn'],
        module='endorsement_party', type_='model')
    Pool.register(
        wizard.StartEndorsement,
        party.PartyReplace,
        wizard.PartyErase,
        module='endorsement_party', type_='wizard')
    Pool.register(
        wizard.StartEndorsementSSN,
        depends=['party_ssn'],
        module='endorsement_party', type_='wizard')

    Pool.register(
        api.APIConfiguration,
        api.APIEndorsement,
        module='endorsement_party', type_='model', depends=['api'])
