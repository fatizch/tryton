import random
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, coop_string


MODULE_NAME = 'bank_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    number_of_banks = fields.Integer('Number of Banks')

    @classmethod
    def add_address(cls, line, bank):
        Address = Pool().get('party.address')
        address = Address()
        address.name = line[11:49].strip()
        address.line3 = line[88:120].strip()
        address.street = line[120:152].strip().upper()
        address.streetbis = line[152:184].strip().upper()
        address.zip = line[184:189].strip().upper()
        address.city = line[190:216].strip().upper()
        country_code = coop_string.check_for_pattern(line[240:242],
            r'^[A-Z]{2}')
        if country_code:
            address.country = cls.get_country_by_code(country_code)
        else:
            address.country = None
        cls.create_zip_code_if_necessary(address)
        bank.addresses = [address]

    @classmethod
    def new_company(cls, name, short_name='', child_level=None,
            cur_depth=None):
        result = super(TestCaseModel, cls).new_company(name, short_name,
            child_level, cur_depth)
        result.currency = cls.get_instance().currency
        return result

    @classmethod
    def create_bank(cls, **kwargs):
        Bank = Pool().get('bank')
        return Bank(**kwargs)

    @classmethod
    def new_bank(cls, line, existing_bics):
        bic = line[236:247].rstrip().replace(' ', '')
        if not bic or bic in existing_bics:
            return
        company = cls.new_company(line[11:51].strip(),
            line[51:61].strip())
        address = cls.create_address(
            name=line[11:49].strip(),
            line3=line[88:120].strip(),
            street=line[120:152].strip().upper(),
            streetbis=line[152:184].strip().upper(),
            zip=line[184:189].strip().upper(),
            city=line[190:216].strip().upper(),
            country=cls.get_country_by_code(line[240:242]),
            )
        company.addresses = [address]
        bank = cls.create_bank(party=company, bic=bic)
        existing_bics[bank.bic] = bank
        return bank

    @classmethod
    def bank_test_case(cls):
        Bank = Pool().get('bank')
        Configuration = cls.get_instance()
        cls.load_resources(MODULE_NAME)
        bank_file = cls.read_list_file('bank.cfg', MODULE_NAME)
        existing = dict((x.bic, x) for x in Bank.search([]))
        banks = []
        for line in bank_file:
            if (Configuration.number_of_banks > 0
                    and len(existing) >= Configuration.number_of_banks):
                break
            bank = cls.new_bank(line, existing)
            if bank:
                banks.append(bank)

        bank_file = cls.read_csv_file('bank.csv', MODULE_NAME,
            reader='dict')
        for bank_dict in bank_file:
            if (Configuration.number_of_banks > 0
                    and len(existing) >= Configuration.number_of_banks):
                break
            if bank_dict['bic'] in existing:
                continue
            company = cls.new_company(bank_dict['party'])
            bank = cls.create_bank(party=company, bic=bank_dict['bic'])
            existing[bank.bic] = bank
            banks.append(bank)
        Bank.create([x._save_values for x in banks])

    @classmethod
    def bank_test_case_test_method(cls):
        Bank = Pool().get('bank')
        Configuration = cls.get_instance()
        return (Configuration.number_of_banks == -1
            or Configuration.number_of_banks > Bank.search_count([]))

    @classmethod
    def create_bank_account(cls, **kwargs):
        BankAccount = Pool().get('bank.account')
        return BankAccount(**kwargs)

    @classmethod
    def create_bank_account_number(cls, **kwargs):
        BankAccountNumber = Pool().get('bank.account.number')
        return BankAccountNumber(**kwargs)

    @classmethod
    def new_bank_account(cls, party, banks):
        bank_code = str(random.randint(0, 99999)).zfill(5)
        bank = random.choice(banks)
        branch_code = str(random.randint(0, 999)).zfill(5)
        account_number = str(random.randint(0, 99999999)).zfill(11)
        key = str(97 - (89 * int(bank_code) + 15 * int(branch_code)
                + 3 * int(account_number)) % 97).zfill(2)
        number = cls.create_bank_account_number(type='iban',
            number='FR76%s%s%s%s' % (bank_code, branch_code, account_number,
                key))
        account = cls.create_bank_account(currency=cls.get_instance().currency,
            owners=[party], numbers=[number], number=number.number, bank=bank)
        return account

    @classmethod
    def bank_account_test_case(cls):
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')
        BankAccount = pool.get('bank.account')
        parties = Party.search([('bank_accounts', '=', None)])
        banks = Bank.search([])
        accounts = []
        for party in parties:
            accounts.append(cls.new_bank_account(party, banks))
        BankAccount.create([x._save_values for x in accounts])
