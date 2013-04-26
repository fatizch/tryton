from trytond.pool import PoolMeta

__all__ = [
    'LoanClaimDeliveredService',
    'LoanIndemnification',
]


class LoanClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

        #TODO: Temporary hack
    def get_loan(self):
        for covered_data in self.subscribed_service.covered_data:
            for share in covered_data.loan_shares:
                return share.loan

    def is_loan(self):
        return self.subscribed_service.is_loan

    def init_dict_for_rule_engine(self, cur_dict):
        super(LoanClaimDeliveredService, self).init_dict_for_rule_engine(
            cur_dict)
        if not self.is_loan():
            return
        cur_dict['loan'] = self.get_loan()


class LoanIndemnification():
    'Indemnification'

    __name__ = 'ins_claim.indemnification'
    __metaclass__ = PoolMeta

    def init_from_delivered_service(self, delivered_service):
        super(LoanIndemnification, self).init_from_delivered_service(
            delivered_service)
        if not delivered_service.is_loan():
            return
        self.beneficiary = delivered_service.get_loan().lender
