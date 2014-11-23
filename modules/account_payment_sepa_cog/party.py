from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.model import fields
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    is_sepa_creditor_identifier_needed = fields.Function(
        fields.Boolean('Need SEPA Creditor Identifier'),
        'get_is_sepa_creditor_identifier_needed')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.sepa_creditor_identifier.states = {
            'invisible': ~Eval('is_sepa_creditor_identifier_needed'),
            }
        cls.sepa_creditor_identifier.depends.append(
            'is_sepa_creditor_identifier_needed')

    def get_is_sepa_creditor_identifier_needed(self, name):
        return self.id == Transaction().context.get('company', -1)
