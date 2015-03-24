from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'ChangeBillingAccount',
    ]


class ChangeBillingAccount:
    __name__ = 'contract.bank_account.change'

    def generate_endorsement(self):
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        BillingEndorsement = pool.get(
            'endorsement.contract.billing_information')
        data = self.select_new_account
        values = []
        contracts = [data.contract] + list(data.other_contracts)
        for contract in contracts:
            endorsement_values = []
            billing_values = contract._save_values['billing_informations']
            for action, billing_value in billing_values:
                if action == 'delete':
                    for to_del in billing_value:
                        endorsement_values.append(BillingEndorsement(
                                action='remove', relation=to_del))
                elif action == 'create':
                    for dict_val in billing_value:
                        new_dict = dict_val.copy()
                        new_dict.pop('contract', None)
                        endorsement_values.append(
                            BillingEndorsement(action='add', values=new_dict))
                elif action == 'write':
                    id_to_write, values_to_write = billing_value
                    endorsement_values.append(
                        BillingEndorsement(action='update',
                            relation=id_to_write[0],
                            values=values_to_write.copy()))
            values.append({'billing_informations': endorsement_values})
        endorsement = ContractEndorsement.new_rollback_point(contracts,
            data.effective_date, 'endorsement_insurance_invoice.' +
            'change_bank_account_definition', values)
        endorsement.save()

    def save_contracts(self):
        self.generate_endorsement()
        super(ChangeBillingAccount, self).save_contracts()
