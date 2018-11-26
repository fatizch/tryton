# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils

__all__ = [
    'Contract',
    'Endorsement',
    ]


class Endorsement(metaclass=PoolMeta):
    __name__ = 'endorsement'

    @classmethod
    def handle_sepa_change(cls, contract_endorsements):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')
        all_new_mandates = []
        for contract_endorsement in contract_endorsements:
            billing_infos = contract_endorsement.billing_informations
            if not billing_infos:
                continue
            mandates_written = Mandate.browse([x.values.get('sepa_mandate')
                for x in billing_infos if x.values.get('sepa_mandate', False)])
            new_mandates = [x for x in mandates_written if x.state == 'draft']
            if not new_mandates:
                continue
            all_new_mandates.extend(new_mandates)
        if all_new_mandates:
            Mandate.write(all_new_mandates, {'state': 'validated'})

    @classmethod
    def pre_apply_hook(cls, endorsements_per_model):
        super(Endorsement, cls).pre_apply_hook(endorsements_per_model)
        contract_endorsements = endorsements_per_model['endorsement.contract']
        cls.handle_sepa_change(contract_endorsements)


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({'amended_mandates':
                'Mandates with identification %s are amended. '
                'Please use the newer version or generate '
                'a new mandate for this contract.'})

    def before_activate(self):
        super(Contract, self).before_activate()
        # Checking that there are no amended mandates should only be done when
        # it is a contract's first activation. If the contract is reactivated
        # after it has been suspended or terminated, its behaviour should not
        # change.
        if self.status == 'quote':
            self.check_no_amended_mandates()

    def check_no_amended_mandates(self):
        Mandate = Pool().get('account.payment.sepa.mandate')
        mandates = []
        today = utils.today()
        billing_informations = self.billing_informations
        billing_infos = sorted(billing_informations, key=lambda x: x.date
            if x.date else datetime.date.min, reverse=True)
        for b in billing_infos:
            if b.sepa_mandate:
                mandates.append(b.sepa_mandate.id)
            if not b.date or b.date <= today:
                break
        if not mandates:
            return
        amendments = Mandate.search([('amendment_of', 'in', mandates)])
        if amendments:
            self.raise_user_error('amended_mandates', ', '.join(
                    set(x.identification for x in mandates)))
