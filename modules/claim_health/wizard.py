from trytond.pool import PoolMeta


__all__ = [
    'ModifyCoveredElementInformation',
    ]
__metaclass__ = PoolMeta


class ModifyCoveredElementInformation:
    __name__ = 'endorsement.contract.covered_element.modify'

    @classmethod
    def _covered_element_fields_to_extract(cls):
        return super(ModifyCoveredElementInformation, cls).\
            _covered_element_fields_to_extract() + \
            ['claim_specific_bank_account']

    def init_covered_default_value(self, covered):
        values = super(ModifyCoveredElementInformation, self).\
            init_covered_default_value(covered)
        if covered.claim_default_bank_account:
            values['claim_default_bank_account'] = \
                covered.claim_default_bank_account.id
        if covered.claim_bank_account:
            values['claim_bank_account'] = covered.claim_bank_account.id
        values['possible_claim_bank_accounts'] = [account.id for account in
            covered.possible_claim_bank_accounts]
        return values
