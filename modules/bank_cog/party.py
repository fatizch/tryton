import copy

from sql.aggregate import Max
from sql import Literal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, PYSONEncoder, Not, Bool

from trytond.modules.cog_utils import coop_string, fields, utils, model
from trytond.modules.cog_utils import UnionMixin
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

    bank_role = fields.One2Many('bank', 'party', 'Bank', states={
            'invisible': ~Eval('is_bank', False) | Not(STATES_COMPANY)},
        depends=['is_bank', 'is_company'])
    is_bank = fields.Function(
        fields.Boolean('Is Bank',
            states={'invisible': Not(STATES_COMPANY)}),
        'get_is_actor', setter='set_is_actor', searcher='search_is_actor')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/notebook/page[@id="role"]/notebook/page[@id="bank"]',
                'states',
                {'invisible': Bool(~Eval('is_bank'))}
                )]

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        default.setdefault('bank_role', None)
        return super(Party, cls).copy(parties, default=default)

    @fields.depends('is_bank')
    def on_change_is_bank(self):
        self._on_change_is_actor('is_bank')

    def get_summary_content(self, label, at_date=None, lang=None):
        res = super(Party, self).get_summary_content(label, at_date, lang)
        res[1].append(coop_string.get_field_summary(self, 'bank_accounts',
                True, at_date, lang))
        if self.bank_role:
            res[1].append(coop_string.get_field_summary(self, 'bank_role',
                    True, at_date, lang))
        return res

    def get_bank_account(self, at_date=None):
        return utils.get_good_version_at_date(self, 'bank_accounts', at_date)

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

    def get_icon(self, name=None):
        if self.is_bank:
            return'bank'
        return super(Party, self).get_icon(name)

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Party, cls).search_global(text):
            if record.is_bank:
                continue
            yield record, rec_name, record.get_icon()

    def get_rec_name(self, name):
        if self.is_bank:
            return self.full_name
        return super(Party, self).get_rec_name(name)


class SynthesisMenuBankAccoount(model.CoopSQL):
    'Party Synthesis Menu Bank Account'
    __name__ = 'party.synthesis.menu.bank_account'

    name = fields.Char('Bank Account')
    owner = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

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

    def get_rec_name(self, name):
        BankAccountSynthesis = Pool().get('party.synthesis.menu.bank_account')
        return coop_string.translate_label(BankAccountSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.bank_account',
            'bank.account-party.party',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if (Model.__name__ == 'party.synthesis.menu.bank_account'):
            if name == 'parent':
                return Model._fields['owner']
        elif Model.__name__ == 'bank.account-party.party':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['owner'])
                union_field.model_name = 'party.synthesis.menu.bank_account'
                return union_field
            elif name == 'name':
                return Model._fields['account']
        return union_field

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
                'res_id': [record.account.id],
            }
        return actions
