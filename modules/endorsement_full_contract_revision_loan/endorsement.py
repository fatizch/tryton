from trytond.pool import PoolMeta
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'Loan',
    ]


class Loan:
    __name__ = 'loan'

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls._error_messages.update({
                'concurrent_modification': 'The loan is currently used on '
                'contract %(contract)s, which is being modified by '
                'user %(user)s',
                })

    @classmethod
    def check_loan_is_used(cls, loans):
        super(Loan, cls).check_loan_is_used(loans)
        for loan in loans:
            quote_contracts = set([(x.contract.rec_name,
                        (x.write_uid or x.create_uid).rec_name)
                    for x in loan.loan_shares
                    if x.contract.status == 'quote'
                    and x.contract.write_uid.id != Transaction().user])
            for contract_name, user_name in quote_contracts:
                cls.append_functional_error('concurrent_modification',
                    {'contract': contract_name, 'user': user_name})
