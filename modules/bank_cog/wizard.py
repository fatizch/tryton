# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = [
    'PartyErase',
    ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        pool = Pool()
        BankAccountParty = pool.get('bank.account-party.party')
        BankAccountNumber = pool.get('bank.account.number')
        party_accounts = BankAccountParty.search([
                ('owner', '=', party_id)])
        accounts_to_erase = [b.account.id for b in party_accounts
            if len(b.account.owners) == 1]
        account_numbers_to_erase = [n.id for n in BankAccountNumber.search([
                    ('account', 'in', accounts_to_erase)])]
        to_erase.append(
            (BankAccountNumber, [('id', 'in', account_numbers_to_erase)], True,
                ['number'],
                [None]))
        return to_erase

    def transition_erase(self):
        pool = Pool()
        Party = pool.get('party.party')
        BankAccountParty = pool.get('bank.account-party.party')
        parties = replacing = [self.ask.party]
        with Transaction().set_context(active_test=False):
            while replacing:
                replacing = Party.search([
                        ('replaced_by', 'in', map(int, replacing))
                        ])
                parties += replacing
        for party in parties:
            self.check_erase(party)
        accounts_parties_to_break = [x
            for x in BankAccountParty.search([('owner', 'in', parties)])
            if len(x.account.owners) > 1]
        if accounts_parties_to_break:
            cursor = Transaction().connection.cursor()
            account_party = BankAccountParty.__table__()
            cursor.execute(*account_party.delete(
                    where=account_party.id.in_(accounts_parties_to_break)))
        return super(PartyErase, self).transition_erase()
