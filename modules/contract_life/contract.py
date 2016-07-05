# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.pool import Pool, PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        # TODO : Move to claim ?
        res = super(Contract, cls).get_possible_contracts_from_party(party,
            at_date)
        if not party:
            return res
        for cov_elem in cls.get_possible_covered_elements(party, at_date):
            contract = cov_elem.main_contract
            # TODO : Temporary Hack Date validation should be done with domain
            # and in get_possible_covered_elements
            if (contract and contract.status == 'active'
                    and contract.start_date <= at_date <= (
                        contract.end_date or datetime.date.max)):
                if contract not in res:
                    res.append(contract)
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        # TODO : Move to claim ?
        CoveredElement = Pool().get('contract.covered_element')
        return CoveredElement.get_possible_covered_elements(party, at_date)

    def get_default_contacts(self, type_=None, at_date=None):
        Contact = Pool().get('contract.contact')
        contacts = super(Contract, self).get_default_contacts(type_, at_date)
        if type_ and type_ != 'covered_party':
            return contacts
        parties = set([])
        for covered_element in [x for x in self.covered_elements if x.party]:
            for option in covered_element.options:
                if option.start_date <= at_date and option.end_date > at_date:
                    parties.add(covered_element.party)
        for p in parties:
            contacts.append(Contact(
                    party=p,
                    type_code='covered_party',
                    ))
        return contacts


class ContractOption:
    __name__ = 'contract.option'

    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'on_change_with_person')

    @fields.depends('covered_element')
    def on_change_with_person(self, name=None):
        if self.covered_element and self.covered_element.party:
            return self.covered_element.party.id
