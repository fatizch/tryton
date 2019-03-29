# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import utils, fields

__all__ = [
    'Contract',
    'ContractVersion',
    'Option',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    claim_bank_account = fields.Function(
        fields.Many2One('bank.account', 'Claim Bank Account',
            states={
                'readonly': ~Eval('claims_paid_to_subscriber') | (
                    Eval('status') != 'quote') | ~Eval('subscriber'),
                'invisible': ~Eval('claims_paid_to_subscriber'),
                },
            domain=[('owners', '=', Eval('subscriber'))],
            depends=['subscriber', 'claims_paid_to_subscriber', 'status'],
            help='The default bank account that will be used to pay claims '
            'related to this contract'),
        'get_extra_data', setter='setter_void')
    claims_paid_to_subscriber = fields.Function(
        fields.Boolean('Claims paid to subscriber',
            help='Returns True if at least one benefit on the product will '
            'be paid to the subscriber'),
        'getter_claims_paid_to_subscriber')
    claims = fields.Function(
        fields.Many2Many('claim', None, None, 'Claims'),
        'get_claims')

    def get_possible_benefits(self, loss):
        res = []
        for option in self.options:
            res.extend(option.get_possible_benefits(loss))
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                res.extend(option.get_possible_benefits(loss))
        return list(set(res))

    @classmethod
    def get_extra_data(cls, contracts, names):
        values = super().get_extra_data(contracts, names)
        if 'claim_bank_account' not in values:
            return values
        for contract in contracts:
            if values['claim_bank_account'][contract.id]:
                continue
            bank_account = contract._get_default_claim_bank_account()
            if bank_account:
                values['claim_bank_account'][contract.id] = bank_account.id
        return values

    def _get_default_claim_bank_account(self, at_date=None):
        if not self.subscriber:
            return None
        at_date = at_date or utils.today()
        return self.subscriber.get_bank_account(at_date=at_date)

    def getter_claims_paid_to_subscriber(self, name):
        return self.product.indemnifications_paid_to_subscriber()

    def get_claims(self, name):
        Service = Pool().get('claim.service')
        services = Service.search(['contract', '=', self.id])
        return [service.loss.claim.id for service in services]

    @fields.depends('claim_bank_account', 'extra_datas', 'initial_start_date',
        'subscriber')
    def on_change_claim_bank_account(self):
        if not self.extra_datas:
            return
        current_version = utils.get_value_at_date(self.extra_datas,
            self.initial_start_date or utils.today())
        if not current_version:
            return
        if not self.subscriber or not self.claim_bank_account:
            value = None
        else:
            default_bank_account = self._get_default_claim_bank_account()
            value = self.claim_bank_account
            if default_bank_account == self.claim_bank_account:
                value = None
        current_version.claim_bank_account = value
        self.extra_datas = list(self.extra_datas)

    @fields.depends('claim_bank_account', 'extra_datas', 'initial_start_date',
        'subscriber')
    def on_change_subscriber(self):
        super().on_change_subscriber()
        self.claim_bank_account = None
        self.on_change_claim_bank_account()
        self.claim_bank_account = self._get_default_claim_bank_account()

    def get_claim_bank_account_at_date(self, at_date=None):
        version = utils.get_value_at_date(self.extra_datas, at_date or
            utils.today())
        account = None
        if version:
            account = version.claim_bank_account
        if account:
            return account
        return self._get_default_claim_bank_account(at_date=at_date)


class ContractVersion(metaclass=PoolMeta):
    __name__ = 'contract.extra_data'

    claim_bank_account = fields.Many2One('bank.account', 'Claim Bank Account',
        ondelete='RESTRICT', states={
            'readonly': Bool(Eval('contract_status')) & (
                Eval('contract_status') != 'quote'),
            }, depends=['contract_status'])

    @classmethod
    def revision_columns(cls):
        return super().revision_columns() + ['claim_bank_account']


class Option(metaclass=PoolMeta):
    __name__ = 'contract.option'

    benefits = fields.Function(
        fields.Many2Many('benefit', None, None, 'Benefits'),
        'get_benefits_ids')

    def is_item_covered(self, loss):
        return utils.is_effective_at_date(self, at_date=loss.get_date())

    def get_possible_benefits(self, loss):
        res = []
        for benefit in self.coverage.get_possible_benefits(
                loss.loss_desc, loss.event_desc, loss.get_date()):
            res.append((benefit, self))
        return res

    def get_benefits_ids(self, name):
        return [x.id for x in self.coverage.benefits] if self.coverage else []
