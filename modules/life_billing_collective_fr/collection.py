from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'CollectionCreate',
    ]


class CollectionCreate:
    __name__ = 'collection.create'

    def default_input_collection_parameters(self, name):
        res = super(CollectionCreate,
            self).default_input_collection_parameters(name)
        the_model = Transaction().context.get('active_model', None)
        if not the_model or the_model != 'billing.premium_rate.form':
            return res
        rate_note = Pool().get(the_model)(
            Transaction().context.get('active_id'))
        res['contract'] = rate_note.contract.id
        res['party'] = rate_note.contract.subscriber.id
        res['amount'] = rate_note.amount_expected
        res['kind'] = 'check'
        return res
