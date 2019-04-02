# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields, utils

__all__ = [
    'ClaimService',
    'Indemnification',
    'ClaimServiceExtraDataRevision',
    ]


class ClaimService(metaclass=PoolMeta):
    __name__ = 'claim.service'

    def getter_is_a_complement(self, name):
        if self.option.previous_claims_management_rule not in (
                'in_complement', 'in_complement_previous_rule'):
            return super().getter_is_a_complement(name)
        return self.loss.get_date() < self.option.initial_start_date

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if (not self.benefit.is_group or
                self.benefit.benefit_rules[0].force_annuity_frequency):
            return
        option_benefit = self.option.get_version_at_date(
            self.loss.start_date).get_benefit(self.benefit)
        self.annuity_frequency = option_benefit.annuity_frequency if not \
            self.benefit.benefit_rules[0].force_annuity_frequency else \
            self.benefit.benefit_rules[0].annuity_frequency

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

    def get_beneficiaries_data(self, at_date):
        covered = self.theoretical_covered_element
        if self.benefit.beneficiary_kind == 'subsidiaries_then_covered':
            if not covered.contract_exit_date or (
                        covered.contract_exit_date and
                        covered.contract_exit_date > at_date):
                return [(x.party, 1)
                    for x in covered.all_parents if x.party is not None] or \
                    [(covered.party, 1)]
            else:
                return [(covered.party, 1)]
        if self.benefit.beneficiary_kind == 'subsidiaries_covered_subscriber':
            return [(x.party, 1)
                for x in covered.all_parents if x.party is not None] \
                + [(self.option.parent_contract.subscriber, 1)] \
                + [(covered.party, 1)]
        return super(ClaimService, self).get_beneficiaries_data(at_date)

    def getter_may_have_origin(self, name):
        result = super().getter_may_have_origin(name)
        if not result or not self.benefit.is_group:
            return result
        # Check whether the option requires this behavior
        if not self.option:
            return False
        return (self.option.previous_claims_management_rule ==
            'in_complement_previous_rule')


class Indemnification(metaclass=PoolMeta):
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
                'missing_origin_service': 'The origin service must be set '
                'prior to calculation for %(service)s',
                })

    def get_possible_products(self):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(Indemnification, self).get_possible_products()
        return self.service.benefit.company_products if self.service else []

    @fields.depends('beneficiary', 'possible_products', 'product', 'service')
    def on_change_beneficiary(self):
        if not self.service and not self.beneficiary:
            return
        self.__class__.update_product(self)

    def getter_bank_account(self, name):
        if (self.journal and self.journal.needs_bank_account()
                and self.service.benefit.beneficiary_kind ==
                'subscriber_then_covered'
                and self.beneficiary == self.service.contract.subscriber):
            invoice = self._invoice()
            date = invoice.invoice_date if invoice else utils.today()
            account = self.service.contract.get_claim_bank_account_at_date(
                at_date=date)
            return account.id if account else None
        return super().getter_bank_account(name)

    @classmethod
    def covered_elements_per_party_contract(cls, indemnifications):
        covered_elements = {}

        def group_by_party_contract(x):
            return (x.contract, x.party)

        elements = sorted([x.service.theoretical_covered_element for x in
                indemnifications if x.service.theoretical_covered_element],
                key=group_by_party_contract)
        for key, sub_elements in groupby(elements, group_by_party_contract):
            covered_elements[key] = elements[0] if elements else None
        return covered_elements

    @classmethod
    def _get_delta_indemnifications(cls, indemnification,
            previous_indemnification):
        delta = super(Indemnification, cls)._get_delta_indemnifications(
            indemnification, previous_indemnification)
        option = indemnification.service.option
        if option.previous_claims_management_rule not in ('in_complement',
                'in_complement_previous_rule'):
            return delta
        delta = 0
        if (not previous_indemnification and
                indemnification.service.loss.has_end_date):
            delta = (indemnification.start_date -
                max(indemnification.service.loss.start_date,
                    option.start_date)).days + 1
        if (previous_indemnification and
                previous_indemnification.service.loss.has_end_date):
            delta = (indemnification.start_date -
                max(previous_indemnification.end_date, option.start_date)
                ).days
        return delta

    @classmethod
    def check_schedulability(cls, indemnifications):
        super(Indemnification, cls).check_schedulability(indemnifications)
        for indemn in indemnifications:
            option = indemn.service.option
            if option.previous_claims_management_rule in (
                    'in_complement', 'in_complement_previous_rule'):
                if indemn.start_date < option.start_date:
                    cls.raise_user_error('before_option_start_date', {
                            'indemnification': indemn.rec_name,
                            })

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
                        (indemnification.end_date or datetime.date.min) >
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
        cls._check_origin_service(indemnifications)

    @classmethod
    def _check_origin_service(cls, indemnifications):
        for indemnification in indemnifications:
            service = indemnification.service
            if not service.is_a_complement:
                continue
            if not service.origin_service:
                cls.raise_user_error('missing_origin_service',
                    {'service': service.rec_name})

    @classmethod
    @ModelView.button
    def validate_indemnification(cls, indemnifications):
        for indemn in indemnifications:
            option = indemn.service.option
            if (option.previous_claims_management_rule in (
                        'in_complement', 'in_complement_previous_rule')
                    and indemn.start_date < option.start_date):
                cls.raise_user_error('before_option_start_date', {
                        'indemnification': indemn.rec_name,
                        })
        super(Indemnification, cls).validate_indemnification(indemnifications)


class ClaimServiceExtraDataRevision(metaclass=PoolMeta):
    __name__ = 'claim.service.extra_data'

    previous_insurer_base_amount = fields.Numeric(
        'Previous Insurer Base Amount',
        digits=(16, Eval('currency_digits', 2)),
        states={'invisible': Bool(Eval('previous_insurer_amount_invisible'))},
        depends=['currency_digits', 'previous_insurer_amount_invisible'])
    previous_insurer_revaluation = fields.Numeric(
        'Previous Insurer Revaluation Amount',
        digits=(16, Eval('currency_digits', 2)),
        states={'invisible': Bool(Eval('previous_insurer_amount_invisible'))},
        depends=['currency_digits', 'previous_insurer_amount_invisible'])
    previous_insurer_amount_invisible = fields.Function(fields.Boolean(
            'Previous Insurer Amount Invisible'),
        'getter_previous_amount_invisible')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            readonly=True), 'getter_currency_digits')

    def getter_currency_digits(self, name):
        return self.claim_service.currency_digits

    def getter_previous_amount_invisible(self, name):
        if not self.claim_service:
            return True
        if self.claim_service.option.previous_claims_management_rule in (
                'in_complement', 'in_complement_previous_rule'):
            return False
        return True
