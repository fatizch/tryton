import datetime
from proteus import Model

__all__ = ['create_party_person']


def add_accounts(person, company):
    Account = Model.get('account.account')
    AccountKind = Model.get('account.account.type')

    product_account_kind = AccountKind()
    product_account_kind.name = 'Product Account Kind'
    product_account_kind.company = company
    product_account_kind.save()
    receivable_account_kind = AccountKind()
    receivable_account_kind.name = 'Receivable Account Kind'
    receivable_account_kind.company = company
    receivable_account_kind.save()
    payable_account_kind = AccountKind()
    payable_account_kind.name = 'Payable Account Kind'
    payable_account_kind.company = company
    payable_account_kind.save()

    product_account = Account()
    product_account.name = 'Product Account'
    product_account.code = 'product_account'
    product_account.kind = 'revenue'
    product_account.type = product_account_kind
    product_account.company = company
    product_account.save()
    receivable_account = Account()
    receivable_account.name = 'Account Receivable'
    receivable_account.code = 'account_receivable'
    receivable_account.kind = 'receivable'
    receivable_account.reconcile = True
    receivable_account.type = receivable_account_kind
    receivable_account.company = company
    receivable_account.save()
    payable_account = Account()
    payable_account.name = 'Account Payable'
    payable_account.code = 'account_payable'
    payable_account.kind = 'payable'
    payable_account.type = payable_account_kind
    payable_account.company = company
    payable_account.save()
    person.account_receivable = receivable_account
    person.account_payable = payable_account


def create_party_person(name=None, first_name=None, birth_date=None,
        company=None):
    "Create default party person"
    Party = Model.get('party.party')

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
    if hasattr(person, 'account_payable'):
        add_accounts(person, company)
    person.save()
    return person
