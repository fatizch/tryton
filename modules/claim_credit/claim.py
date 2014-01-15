from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ClaimIndemnification',
    ]


class ClaimIndemnification:
    __name__ = 'claim.indemnification'

    def init_from_service(self, service):
        super(ClaimIndemnification, self).init_from_service(
            service)
        if not service.is_loan:
            return
        self.beneficiary = service.loan.lender.party
