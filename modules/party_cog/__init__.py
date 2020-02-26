# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from sql import Literal
from sql.operators import Concat
from sql.conditionals import Coalesce

from trytond.pool import Pool

from . import party
from . import category
from . import contact_mechanism
from . import country
from . import address
from . import test_case
from . import relationship
from . import res
from . import attachment
from . import configuration
from . import batch
from . import api

from trytond.modules.coog_core import expand_tree

PartyMenuTreeExpansion = expand_tree('party.synthesis.menu')


def register():
    Pool.register(
        res.User,
        party.Party,
        party.PartyLang,
        party.PartyIdentifier,
        party.PartyIdentifierType,
        category.PartyCategory,
        country.Country,
        country.CountryAddressLine,
        address.Address,
        address.Zip,
        contact_mechanism.ContactMechanism,
        contact_mechanism.PartyInteraction,
        test_case.TestCaseModel,
        test_case.GlobalSearchSet,
        relationship.RelationType,
        relationship.PartyRelation,
        relationship.PartyRelationAll,
        attachment.Attachment,
        party.SynthesisMenuActionCloseSynthesis,
        party.SynthesisMenuActionRefreshSynthesis,
        party.SynthesisMenuContact,
        party.SynthesisMenuAddress,
        party.SynthesisMenuPartyInteraction,
        party.SynthesisMenuRelationship,
        party.SynthesisMenu,
        party.SynthesisMenuOpenState,
        party.ExtractGDPRDataView,
        PartyMenuTreeExpansion,
        party.PartyReplaceAsk,
        configuration.Configuration,
        batch.PartyAnonymizeBatch,
        module='party_cog', type_='model')
    Pool.register(
        party.SynthesisMenuSet,
        party.SynthesisMenuOpen,
        party.ExtractGDPRData,
        party.PartyReplace,
        party.PartyErase,
        module='party_cog', type_='wizard')

    Pool.register(
        api.APIIdentity,
        api.Party,
        api.APICore,
        api.APIParty,
        module='party_cog', type_='model', depends=['api'])

    Pool.register(
        api.APIPartySiret,
        module='party_cog', type_='model', depends=['api', 'party_siret'])

    Pool.register_post_init_hooks(migrate_1_10_include_name_in_street,
        module='party')


def migrate_1_10_include_name_in_street(pool, update):
    if update != 'party':
        return

    from trytond import backend
    from trytond.transaction import Transaction
    from trytond.modules.party.address import Address

    logging.getLogger('modules').info('Running post init hook %s' %
        'migrate_1_10_include_name_in_street')
    previous_register = Address.__register__.__func__

    @classmethod
    def patched_register(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        migrate_name = table.column_exist('streetbis')

        previous_register(cls, module_name)

        # Migration from 1.10 : merge name into street
        if migrate_name:
            value = Concat(Coalesce(sql_table.name, ''),
                Concat('\n', Coalesce(sql_table.street, '')))
            cursor.execute(*sql_table.update([sql_table.street], [value]))
            cursor.execute(*sql_table.update([sql_table.name], [Literal('')]))

    Address.__register__ = patched_register
