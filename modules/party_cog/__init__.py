# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from sql import Literal
from sql.operators import Concat
from sql.conditionals import Coalesce

from trytond.pool import Pool

import party
import category
import contact_mechanism
import address
import test_case
import relationship
import res
import attachment

from trytond.modules.coog_core import expand_tree

PartyMenuTreeExpansion = expand_tree('party.synthesis.menu')


def register():
    Pool.register(
        res.User,
        party.Party,
        party.PartyIdentifier,
        party.PartyIdentifierType,
        category.PartyCategory,
        address.Address,
        contact_mechanism.ContactMechanism,
        contact_mechanism.PartyInteraction,
        test_case.TestCaseModel,
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
        PartyMenuTreeExpansion,
        party.PartyReplaceAsk,
        module='party_cog', type_='model')
    Pool.register(
        party.SynthesisMenuSet,
        party.SynthesisMenuOpen,
        party.PartyReplace,
        module='party_cog', type_='wizard')

    Pool.register_post_init_hooks(migrate_1_10_include_name_in_street,
        module='party')


def migrate_1_10_include_name_in_street(pool, update):
    if update != 'party':
        return

    from trytond import backend
    from trytond.transaction import Transaction
    from trytond.modules.party import Address

    logging.getLogger('modules').info('Running post init hook %s' %
        'migrate_1_10_include_name_in_street')
    previous_register = Address.__register__.im_func

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
