from trytond.pool import PoolMeta, Pool
from trytond.pyson import Not

from trytond.modules.cog_utils import coop_string, fields, utils
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

    @classmethod
    def ws_create_person(cls, person_dict):
        Bank = Pool().get('bank')
        Currency = Pool().get('currency.currency')
        BankAccount = Pool().get('bank.account')
        bank_account_info = person_dict.get('bank_accounts', None)
        if bank_account_info:
            del person_dict['bank_accounts']
        res = super(Party, cls).ws_create_person(person_dict)
        if not bank_account_info or not res['return']:
            return res
        for cur_bank_account in bank_account_info:
            if cur_bank_account['bank']:
                banks = Bank.search([
                    ('bic', '=', cur_bank_account['bank'])], limit=1)
                if not banks:
                    return {'return': False,
                        'error_code': 'unknown_bic',
                        'error_message': 'No bank found for bic %s' %
                            cur_bank_account['bank'],
                        }
                cur_bank_account['bank'] = banks[0]
            if cur_bank_account['currency']:
                currencies = Currency.search([
                    ('code', '=', cur_bank_account['currency'])])
                if not currencies:
                    return {'return': False,
                        'error_code': 'unknown_currency',
                        'error_message': 'No currency found for code\
                            %s' % cur_bank_account['currency'],
                        }
                cur_bank_account['currency'] = currencies[0]
            cur_bank_account['owners'] = [('add', [res['party_id']])]
            cur_bank_account['numbers'] = [
                ('create', cur_bank_account['numbers'])]
            BankAccount.create([cur_bank_account, ])
            return res
