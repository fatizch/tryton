from trytond.pool import PoolMeta
from trytond.pyson import Not

from trytond.modules.coop_utils import coop_string, fields, utils
from trytond.modules.party_cog.party import STATES_COMPANY

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    bank_role = fields.One2Many(
        'bank', 'party', 'Bank', size=1, states={
            'invisible': Not(STATES_COMPANY),
        })
    main_bank_account = fields.Function(
        fields.Many2One('bank.account', 'Main Bank Account'),
        'get_main_bank_account_id')

    @classmethod
    def _export_force_recreate(cls):
        res = super(Party, cls)._export_force_recreate()
        res.remove('bank_role')
        return res

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.bank_role:
                res[party.id] += coop_string.get_field_as_summary(
                    party, 'bank_role', True, at_date, lang=lang)
            res[party.id] += coop_string.get_field_as_summary(
                party, 'bank_accounts', True, at_date, lang=lang)
        return res

    def get_bank_accounts(self, at_date=None):
        return utils.get_good_versions_at_date(self, 'bank_accounts', at_date)

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Party, cls).get_var_names_for_full_extract()
        res.extend(['bank_accounts'])
        return res

    def get_main_bank_account_id(self, name):
        bank_accounts = self.get_bank_accounts(utils.today())
        return bank_accounts[0].id if bank_accounts else None
