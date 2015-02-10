from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

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

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'sepa_mandates'}

    def get_is_sepa_creditor_identifier_needed(self, name):
        company_id = Transaction().context.get('company', None)
        if company_id is None:
            return
        return self == Pool().get('company.company')(company_id).party
