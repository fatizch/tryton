# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'ClaimService',
    'Indemnification',
    ]


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if (not self.benefit.is_group or
                self.benefit.benefit_rules[0].force_annuity_frequency):
            return
        option_benefit = self.option.get_version_at_date(
            self.loss.start_date).get_benefit(self.benefit)
        self.annuity_frequency = option_benefit.annuity_frequency

    @classmethod
    def transfer_services(cls, matches, at_date):
        '''
            Create new services according to `matches` :
            matches = [
                ('src_benefit', 'src_option', 'target_benefit',
                    'target_option'),
                ]
        '''
        copies = []
        for src_benefit, src_option, target_benefit, target_option in matches:
            to_copy = cls.search([('benefit', '=', src_benefit.id),
                    ('option', '=', src_option.id),
                    ['OR', ('loss.end_date', '=', None),
                        ('loss.end_date', '>=', at_date)]])
            copies += cls.copy(to_copy, default={
                    'benefit': target_benefit.id,
                    'option': target_option.id,
                    'contract': target_option.parent_contract.id,
                    })
        Event = Pool().get('event')
        if copies:
            Event.notify_events(copies, 'transferred_claim_service')
        return copies


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls._error_messages.update({
                'bad_dates': 'The indemnification period (%(indemn_start)s - '
                "%(indemn_end)s) is not compatible with the contract's end "
                'date (%(contract_end)s).',
                'covered_element_rupture': 'The covered element '
                '%(party_rec_name)s is in rupture for the contract '
                '%(contract)s at %(date)s and the beneficiary should be the '
                'covered element itself, not %(benef_rec_name)s',
                'dates_not_in_management': 'The indemnification period '
                '(%(indemn_start)s - %(indemn_end)s) is not compatible with '
                'the claim\'s management period (%(management_start)s - '
                '%(management_end)s).',
                })

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(Indemnification, self).get_possible_products(name)
        return [x.id for x in self.service.benefit.company_products]

    @fields.depends('beneficiary', 'possible_products', 'product', 'service')
    def on_change_beneficiary(self):
        if not self.service and not self.beneficiary:
            return
        self.update_product()

    @classmethod
    def covered_elements_per_party_contract(cls, indemnifications):
        covered_elements = {}

        def group_by_party_contract(x):
            return (x.main_contract, x.party)

        elements = sorted([x.service.theoretical_covered_element for x in
                indemnifications], key=group_by_party_contract)
        for key, sub_elements in groupby(elements, group_by_party_contract):
            covered_elements[key] = elements[0] if elements else None
        return covered_elements

    @classmethod
    def check_calculable(cls, indemnifications):
        super(Indemnification, cls).check_calculable(indemnifications)
        covered_elements = cls.covered_elements_per_party_contract(
            indemnifications)
        pool = Pool()
        Date = pool.get('ir.date')
        lang = pool.get('res.user')(Transaction().user).language
        for indemnification in indemnifications:
            key = (indemnification.service.contract,
                indemnification.service.claim.claimant)
            covered_element = covered_elements[key]
            if (covered_element and covered_element.contract_exit_date and
                    indemnification.beneficiary != covered_element.party and
                    (indemnification.start_date <=
                        covered_element.contract_exit_date and
                        (indemnification.end_date or datetime.date.min) >=
                        covered_element.contract_exit_date)):
                cls.append_functional_error('covered_element_rupture', {
                        'party_rec_name': key[1].rec_name,
                        'contract': key[0].contract_number,
                        'date': Date.date_as_string(
                            covered_element.contract_exit_date, lang),
                        'benef_rec_name': indemnification.beneficiary.rec_name})
            if indemnification.service and indemnification.service.contract:
                contract = indemnification.service.contract
                if (contract.status == 'terminated' and
                        contract.post_termination_claim_behaviour ==
                        'stop_indemnisations' and
                        contract.final_end_date < indemnification.end_date):
                    cls.append_functional_error('bad_dates', {
                            'indemn_start': indemnification.start_date,
                            'indemn_end': indemnification.end_date,
                            'contract_end': contract.end_date})
            if indemnification.service and indemnification.service.claim \
                    and indemnification.service.contract:
                management_start = indemnification.service. \
                    claim.management_start_date
                management_end = indemnification.service. \
                    claim.management_end_date
                management_start_statement = management_start and \
                    indemnification.start_date < management_start
                management_end_statement = management_end and \
                    indemnification.end_date > management_end
                if management_start_statement or management_end_statement:
                    cls.raise_user_warning('dates_not_in_management',
                        'dates_not_in_management', {
                            'indemn_start': indemnification.start_date,
                            'indemn_end': indemnification.end_date,
                            'management_start': management_start,
                            'management_end': management_end})
