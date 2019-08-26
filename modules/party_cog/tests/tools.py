# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from proteus import Model

__all__ = ['create_party_person']


def add_accounts(person, company):
    Account = Model.get('account.account')
    AccountKind = Model.get('account.account.type')

    product_account_kind = AccountKind()
    product_account_kind.name = 'Product Account Kind'
    product_account_kind.company = company
    product_account_kind.statement = 'income'
    product_account_kind.revenue = True
    product_account_kind.save()
    receivable_account_kind = AccountKind()
    receivable_account_kind.name = 'Receivable Account Kind'
    receivable_account_kind.company = company
    receivable_account_kind.statement = 'balance'
    receivable_account_kind.receivable = True
    receivable_account_kind.save()
    payable_account_kind = AccountKind()
    payable_account_kind.name = 'Payable Account Kind'
    payable_account_kind.company = company
    payable_account_kind.statement = 'balance'
    payable_account_kind.payable = True
    payable_account_kind.save()

    product_account = Account()
    product_account.name = 'Product Account'
    product_account.code = 'product_account'
    product_account.type = product_account_kind
    product_account.company = company
    product_account.save()
    receivable_account = Account()
    receivable_account.name = 'Account Receivable'
    receivable_account.code = 'account_receivable'
    receivable_account.type = receivable_account_kind
    receivable_account.party_required = True
    receivable_account.reconcile = True
    receivable_account.company = company
    receivable_account.save()
    payable_account = Account()
    payable_account.name = 'Account Payable'
    payable_account.code = 'account_payable'
    payable_account.type = payable_account_kind
    payable_account.party_required = True
    payable_account.company = company
    payable_account.save()
    person.account_receivable = receivable_account
    person.account_payable = payable_account


def create_party_person(name=None, first_name=None, birth_date=None,
        company=None):
    "Create default party person"
    Party = Model.get('party.party')
    Country = Model.get('country.country')

    if not name:
        name = 'Doe'
    if not first_name:
        first_name = 'John'
    if not birth_date:
        birth_date = datetime.date(1980, 10, 14)
    person = Party(
        name=name,
        first_name=first_name,
        is_person=True,
        gender='male',
        birth_date=birth_date)

    a = person.all_addresses[0]
    a.street = 'Adresse Inconnue'
    a.zip = '99999'
    a.city = 'Bioul'
    a.country, = Country.find([('code', '=', 'FR')]) or [None]

    if hasattr(person, 'account_payable') and company:
        add_accounts(person, company)
    person.save()
    return person


def create_party_company(name=None):
    Party = Model.get('party.party')
    Country = Model.get('country.country')

    if not name:
        name = 'Acme Inc.'

    company = Party(name=name, is_person=False)

    a = company.all_addresses[0]
    a.street = 'Adresse Inconnue'
    a.zip = '99999'
    a.city = 'Bioul'
    a.country, = Country.find([('code', '=', 'FR')])

    company.save()
    return company
