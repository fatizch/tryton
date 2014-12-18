from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'Endorsement',
    ]


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
