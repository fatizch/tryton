from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract():
    __name__ = 'contract'

    def before_activate(self, contract_dict=None):
        super(Contract, self).before_activate()
        #TODO search mandate only if necessary
        if self.subscriber.sepa_mandates or not self.subscriber.bank_accounts:
            return
        Mandate = Pool().get('account.payment.sepa.mandate')
        mandate = Mandate()
        mandate.party = self.subscriber
        mandate.account_number = self.subscriber.bank_accounts[0].numbers[0]
        #TODO manage identification with sequence
        #mandate.identification =
        mandate.type = 'recurrent'
        mandate.signature_date = contract_dict['start_date']
        mandate.state = 'validated'
        mandate.save()
