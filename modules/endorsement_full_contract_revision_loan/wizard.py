from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'StartFullContractRevision',
    ]


class StartFullContractRevision:
    __name__ = 'endorsement.contract.full_revision_start'

    def update_endorsement(self, base_endorsement, wizard):
        super(StartFullContractRevision, self).update_endorsement(
            base_endorsement, wizard)
        LoanEndorsement = Pool().get('endorsement.loan')
        for loan in base_endorsement.contract.used_loans:
            loan_endorsement = LoanEndorsement()
            loan_endorsement.endorsement = base_endorsement.endorsement
            loan_endorsement.loan = loan
            loan_endorsement.save()
