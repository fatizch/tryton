# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
    'ClaimService',
    ]


class Claim(metaclass=PoolMeta):
    __name__ = 'claim'

    possible_legal_entities = fields.Function(
        fields.One2Many('party.party', None, 'Possible Legal Entities'),
        'getter_possible_legal_entities')
    legal_entity = fields.Many2One('party.party', 'Legal Entity',
        domain=[('id', 'in', Eval('possible_legal_entities'))],
        select=True, ondelete='RESTRICT', depends=['possible_legal_entities'])
    interlocutor = fields.Many2One('party.interlocutor', 'Interlocutor',
        ondelete='RESTRICT', domain=[
            ('party', '=', Eval('legal_entity'))
            ], depends=['legal_entity'])
    management_start_date = fields.Date('Management Start Date')
    management_end_date = fields.Date('Management End Date')

    def get_recipients(self):
        recipients = [self.legal_entity] if self.legal_entity else []
        recipients += super(Claim, self).get_recipients()
        return recipients

    def getter_possible_legal_entities(self, name=None):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        contracts = []
        if self.main_contract:
            contracts.append(self.main_contract)
        contracts += [x.contract for x in self.delivered_services]
        if contracts:
            contracts = set(contracts)
            entities = [x.party.id for x in CoveredElement.search([
                        ('contract', 'in', [x.id for x in contracts]),
                        ('party.is_person', '=', False),
                        ])] + [x.subscriber.id for x in contracts
                if x.subscriber]
        else:
            entities = [x.party.id for x in CoveredElement.search(
                [('is_person', '=', False)])]
        return entities


class ClaimService(metaclass=PoolMeta):
    __name__ = 'claim.service'

    def get_beneficiaries_data(self, at_date):
        if self.benefit.beneficiary_kind == 'subscriber_then_covered':
            covered = self.theoretical_covered_element
            if not covered:
                return [(self.contract.subscriber, 1)]
            elif (not covered.contract_exit_date or
                    covered.contract_exit_date >= at_date):
                return [(covered.affiliated_to or
                        covered.contract.subscriber, 1)]
            return [(covered.party, 1)]
        return super(ClaimService, self).get_beneficiaries_data(at_date)
