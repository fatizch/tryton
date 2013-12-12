import random

from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import fields, coop_string


MODULE_NAME = 'coop_bank'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    number_of_banks = fields.Integer('Number of Banks')

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['contact_mechanism_test_case']['dependencies'].add(
            'bank_test_case')
        result['bank_test_case'] = {
            'name': 'Bank Test Case',
            'dependencies': set(['address_kind_test_case']),
        }
        result['bank_account_test_case'] = {
            'name': 'Bank Account Test Case',
            'dependencies': set(['bank_test_case', 'party_test_case',
                    'main_company_test_case']),
        }
        return result

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
    def bank_test_case(cls):
        Bank = Pool().get('bank')
        Configuration = cls.get_instance()
        cls.load_resources(MODULE_NAME)
        bank_file = cls.read_list_file('bank.cfg', MODULE_NAME)
        existing = dict((x.bic, x) for x in Bank.search([]))
        for line in bank_file:
            if len(existing) >= Configuration.number_of_banks:
                break
            try:
                bic = line[236:247].rstrip().replace(' ', '')
                if not bic or bic in existing:
                    continue
                bank = Bank()
                company = cls.create_company(line[11:51].strip(),
                    line[51:61].strip())
                company.currency = Configuration.currency
                cls.add_address(line, company)
                bank.bic = coop_string.check_for_pattern(line[236:247],
                    r'^[0-9A-Z]{8,11}')
                existing[bank.bic] = bank
                company.save()
                bank.party = company
                bank.save()
            except:
                cls.get_logger().warning('Impossible to create bank %s' %
                    line[11:51].strip())
                raise

    @classmethod
    def bank_account_test_case(cls):
        Party = Pool().get('party.party')
        Bank = Pool().get('bank')
        BankAccount = Pool().get('bank.account')
        BankAccountNumber = Pool().get('bank.account.number')
        Configuration = cls.get_instance()
        parties = Party.search([('bank_accounts', '=', None)])
        banks = Bank.search([])
        cls.get_logger().info('Creating %s bank accounts' % len(parties))
        accounts = []
        for party in parties:
            try:
                account = BankAccount()
                account.currency = Configuration.currency
                number = BankAccountNumber()
                number.type = 'iban'
                bank_code = str(random.randint(0, 99999)).zfill(5)
                account.bank = random.choice(banks)
                branch_code = str(random.randint(0, 999)).zfill(5)
                account_number = str(random.randint(0, 99999999)).zfill(11)
                key = str(97 - (89 * int(bank_code) + 15 * int(branch_code)
                        + 3 * int(account_number)) % 97).zfill(2)
                number.number = 'FR76%s%s%s%s' % (bank_code, branch_code,
                    account_number, key)
                account.numbers = [number]
                account.owners = [party]
                account.number = number.number
                accounts.append(account)
            except:
                raise
                cls.get_logger().warning('Unable to create bank account for %s'
                    % party.name)
        return accounts
