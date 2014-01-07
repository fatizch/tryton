from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ClaimIndemnification',
    ]


class ClaimIndemnification:
    __name__ = 'claim.indemnification'

    def init_from_delivered_service(self, delivered_service):
        super(ClaimIndemnification, self).init_from_delivered_service(
            delivered_service)
        if not delivered_service.is_loan:
            return
        self.beneficiary = delivered_service.loan.lender.party
