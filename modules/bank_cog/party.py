import copy

from sql.aggregate import Max
from sql import Literal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Not, PYSONEncoder

from trytond.modules.cog_utils import coop_string, fields, utils, model
from trytond.modules.cog_utils import MergedMixin
from trytond.modules.party_cog.party import STATES_COMPANY
from trytond.wizard import Wizard


__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'SynthesisMenuBankAccoount',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class Party:
    __name__ = 'party.party'

    bank_role = fields.One2Many(
        'bank', 'party', 'Bank', size=1, states={
            'invisible': Not(STATES_COMPANY),
        })

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


class SynthesisMenuBankAccoount(model.CoopSQL):
    'Party Synthesis Menu Bank Account'
    __name__ = 'party.synthesis.menu.bank_account'

    name = fields.Char('Bank Account')
    owner = fields.Many2One('party.party', 'Party')

    @staticmethod
    def table_query():
        pool = Pool()
        BankAccount = pool.get('bank.account-party.party')
        BankAccountSynthesis = pool.get('party.synthesis.menu.bank_account')
        party = pool.get('party.party').__table__()
        bank_account = BankAccount.__table__()
        query_table = party.join(bank_account, 'LEFT OUTER', condition=(
            party.id == bank_account.owner))
        return query_table.select(
            party.id,
            Max(bank_account.create_uid).as_('create_uid'),
            Max(bank_account.create_date).as_('create_date'),
            Max(bank_account.write_uid).as_('write_uid'),
            Max(bank_account.write_date).as_('write_date'),
            Literal(coop_string.translate_label(BankAccountSynthesis, 'name')).
            as_('name'),
            party.id.as_('owner'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'coopengo-bank_account'


class SynthesisMenu(MergedMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def merged_models(cls):
        res = super(SynthesisMenu, cls).merged_models()
        res.extend([
            'party.synthesis.menu.bank_account',
            'bank.account-party.party',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if (Model.__name__ == 'party.synthesis.menu.bank_account'):
            if name == 'parent':
                return Model._fields['owner']
        elif Model.__name__ == 'bank.account-party.party':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['owner'])
                merged_field.model_name = 'party.synthesis.menu.bank_account'
                return merged_field
            elif name == 'name':
                return Model._fields['account']
        return merged_field

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.bank_account':
            res = 4
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if (Model.__name__ != 'party.synthesis.menu.bank_account' and
                Model.__name__ != 'bank.account-party.party'):
            return super(SynthesisMenuOpen, self).get_action(record)
        if Model.__name__ == 'party.synthesis.menu.bank_account':
            domain = PYSONEncoder().encode([('owners', '=', record.id)])
            actions = {
                'res_model': 'bank.account',
                'pyson_domain': domain,
                'views': [(None, 'tree'), (None, 'form')]
            }
        elif Model.__name__ == 'bank.account-party.party':
            actions = {
                'res_model': 'bank.account',
                'views': [(None, 'form')],
                'res_id': record.account.id
            }
        return actions
