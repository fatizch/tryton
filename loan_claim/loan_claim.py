from trytond.pool import PoolMeta

__all__ = [
    'LoanIndemnification',
]


class LoanIndemnification():
    'Indemnification'

    __name__ = 'ins_claim.indemnification'
    __metaclass__ = PoolMeta

    def init_from_delivered_service(self, delivered_service):
        super(LoanIndemnification, self).init_from_delivered_service(
            delivered_service)
        #TDOD: Temporary hack
        for covered_data in delivered_service.subscribed_service.covered_data:
            for share in covered_data.loan_shares:
                self.beneficiary = share.loan.lender
                break
