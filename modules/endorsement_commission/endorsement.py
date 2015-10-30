from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Endorsement',
    'Contract',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def update_commissions_after_endorsement_application(cls, contracts,
            caller=None):
        cls.update_commissions_after_endorsement(contracts, caller,
            kind='apply')

    @classmethod
    def update_commissions_after_endorsement_cancellation(cls, contracts,
            caller=None):
        cls.update_commissions_after_endorsement(contracts, caller,
            kind='draft')

    @classmethod
    def update_commissions_after_endorsement(cls, contracts, endorsements,
            kind):
        if Transaction().context.get('will_be_rollbacked', False):
            return
        if not isinstance(endorsements, (tuple, list)):
            endorsements = [endorsements]
        if endorsements[0].__name__ != 'endorsement.contract':
            return
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')
        for endorsement in endorsements:
            if endorsement.contract not in contracts:
                continue
            previous_agent = endorsement.base_instance.agent
            if not endorsement.contract.agent or not previous_agent:
                continue
            if endorsement.contract.agent == previous_agent:
                continue
            if kind == 'apply':
                from_agent = previous_agent
                to_agent = endorsement.contract.agent
            else:
                from_agent = endorsement.contract.agent
                to_agent = previous_agent
            Commission.modify_agent(Commission.search([
                        ('commissioned_contract', '=',
                            endorsement.contract.id),
                        ('agent', '=', from_agent.id),
                        ('start', '>=',
                            endorsement.endorsement.effective_date),
                        ]), Agent(to_agent))


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind == 'commission':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    def find_parts(self, endorsement_part):
        if endorsement_part.kind == 'commission':
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)
