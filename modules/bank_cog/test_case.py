# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random
import re
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields


MODULE_NAME = 'bank_cog'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    number_of_banks = fields.Integer('Number of Banks')

    @classmethod
    def add_address(cls, line, bank):
        def check_for_pattern(s, pattern):
            if s is not None:
                s = s.strip()
                matchObj = re.match(pattern, s)
                if matchObj:
                    return matchObj.group()
                return False

        Address = Pool().get('party.address')
        address = Address()
        address.street = '\n'.join([
                line[11:49].strip(),
                line[88:120].strip(),
                line[120:152].strip().upper(),
                line[152:184].strip().upper()])
        address.zip = line[184:189].strip().upper()
        address.city = line[190:216].strip().upper()
        country_code = check_for_pattern(line[240:242], r'^[A-Z]{2}')
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
