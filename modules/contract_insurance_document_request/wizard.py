# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'PartyErase',
    ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def transition_erase(self):
        pool = Pool()
        Party = pool.get('party.party')
        parties = replacing = [self.ask.party]
        with Transaction().set_context(active_test=False):
            while replacing:
                replacing = Party.search([
                        ('replaced_by', 'in', map(int, replacing))])
                parties += replacing
        DocumentRequestLine = pool.get('document.request.line')
        for party in parties:
            self.check_erase(party)
            contracts_to_erase = [c.id for c in self.contracts_to_erase(
                    party.id)]
            requests_to_erase = DocumentRequestLine.search([
                    ('contract', 'in', contracts_to_erase)])
            for request in requests_to_erase:
                request.attachment = None
            DocumentRequestLine.save(requests_to_erase)
        return super(PartyErase, self).transition_erase()
