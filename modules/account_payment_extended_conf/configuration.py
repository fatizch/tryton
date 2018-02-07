# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    def get_payment_journal(self, line):
        pool = Pool()
        PartyJournal = pool.get('account.payment.party_journal_relation')
        relations = PartyJournal.search([
                ('party', '=', line.party)
                ], limit=1)
        if relations:
            return relations[0].journal
        return super(Configuration, self).get_payment_journal(line)
