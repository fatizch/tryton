import copy
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields, utils, coop_string

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'ContactHistory',
    ]


class Party():
    'Party'

    __name__ = 'party.party'

    contracts = fields.One2ManyDomain('contract.contract', 'subscriber',
        'Contracts', domain=[('status', '=', 'active')])

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        if not lang:
            lang = utils.get_user_language()
        res = super(Party, cls).get_summary(parties, name, at_date, lang)
        for party in parties:
            res[party.id] += coop_string.get_field_as_summary(
                party, 'contracts', True, at_date, lang=lang)
        return res


class ContactHistory():
    'Contact History'

    __name__ = 'party.contact_history'

    @classmethod
    def __setup__(cls):
        super(ContactHistory, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)
        cls.for_object_ref.selection.append(('contract.contract', 'Contract'))
