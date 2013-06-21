import copy
from trytond.pool import PoolMeta


__all__ = [
    'ContactHistory',
]


class ContactHistory():
    'Contact History'

    __metaclass__ = PoolMeta
    __name__ = 'party.contact_history'

    @classmethod
    def __setup__(cls):
        super(ContactHistory, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)
        cls.for_object_ref.selection.append(('contract.contract', 'Contract'))
