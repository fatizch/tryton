=======================
Loan Contract Creation
=======================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from dateutil.relativedelta import relativedelta
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.party_cog.tests.tools import create_party_person
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.contract_insurance_invoice.tests.tools import \
    ...     add_invoice_configuration
    >>> from trytond.modules.offered.tests.tools import init_product
    >>> from trytond.modules.offered_insurance.tests.tools import \
    ...     add_insurer_to_product
    >>> from trytond.modules.contract.tests.tools import add_quote_number_generator
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.premium.tests.tools import add_premium_rules

Install Modules::

    >>> config = activate_modules(['account_payment_sepa_contract'])

Create country::

    >>> _ = create_country()

Create currenct::

    >>> currency = get_currency(code='EUR')

Create Company::

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create Fiscal Year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> second_fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
    ...     datetime.date.today() + relativedelta(years=1)))
    >>> second_fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> Bank = Model.get('bank')
    >>> Party = Model.get('party.party')
    >>> party_bank = Party()
    >>> party_bank.name = 'Bank'
    >>> party_bank.save()
    >>> bank = Bank()
    >>> bank.party = party_bank
    >>> bank.bic = 'NSMBFRPPXXX'
    >>> bank.save()
    >>> party_bank2 = Party()
    >>> party_bank2.name = 'Bank 2'
    >>> party_bank2.save()
    >>> bank2 = Bank()
    >>> bank2.party = party_bank2
    >>> bank2.bic = 'BDFEFRPP'
    >>> bank2.save()
    >>> Number = Model.get('bank.account.number')
    >>> banks = Bank.find([])
    >>> Account = Model.get('bank.account')
    >>> company_account = Account()
    >>> company_account.bank = bank
    >>> company_account.owners.append(company.party)
    >>> company_account.currency = currency
    >>> company_account.number = 'ES8200000000000000000000'
    >>> company_account.save()
    >>> AccountAccount = Model.get('account.account')
    >>> bank_clearing = AccountAccount(parent=accounts['payable'].parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = accounts['payable'].type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.kind = 'other'
    >>> bank_clearing.save()

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> product = add_insurer_to_product(product)
    >>> product.save()

Create Payment Journal::

    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Journal = Model.get('account.payment.journal')
    >>> journal = Journal()
    >>> journal.name = 'SEPA Journal'
    >>> journal.company = company
    >>> journal.currency = currency
    >>> journal.process_method = 'sepa'
    >>> journal.sepa_payable_flavor = 'pain.001.001.03'
    >>> journal.sepa_receivable_flavor = 'pain.008.001.02'
    >>> journal.sepa_charge_bearer = 'DEBT'
    >>> journal.sepa_bank_account_number = company_account.numbers[0]
    >>> journal.failure_billing_mode, = BillingMode.find([('code', '=',
    ...     'monthly')])
    >>> journal.save()
    >>> Configuration = Model.get('account.configuration')
    >>> configuration = Configuration(1)
    >>> configuration.direct_debit_journal = journal
    >>> configuration.save()
    >>> AccountJournal = Model.get('account.journal')
    >>> expense, = AccountJournal.find([('code', '=', 'EXP')])
    >>> journal.clearing_account = bank_clearing
    >>> journal.clearing_journal = expense
    >>> journal.save()
    >>> FailureAction = Model.get('account.payment.journal.failure_action')
    >>> RejectReason = Model.get('account.payment.journal.reject_reason')
    >>> reject_reason = RejectReason()
    >>> reject_reason_2 = RejectReason()
    >>> reject_reason.code = 'reject_reason_code'
    >>> reject_reason.description = 'Reject Reason'
    >>> reject_reason.payment_kind = 'receivable'
    >>> reject_reason.process_method = 'sepa'
    >>> reject_reason.save()
    >>> reject_reason_2.code = 'reject_reason_2_code'
    >>> reject_reason_2.description = 'Reject Reason 2'
    >>> reject_reason_2.payment_kind = 'receivable'
    >>> reject_reason_2.process_method = 'sepa'
    >>> reject_reason_2.save()
    >>> insufficient_fund_reject_1 = FailureAction()
    >>> insufficient_fund_reject_1.reject_reason = reject_reason
    >>> insufficient_fund_reject_1.action = 'suspend'
    >>> insufficient_fund_reject_1.reject_number = 1
    >>> insufficient_fund_reject_1.journal = journal
    >>> insufficient_fund_reject_1.save()

This failure action will not automatically un-suspend billing_info::

    >>> insufficient_fund_reject_2 = FailureAction()
    >>> insufficient_fund_reject_2.reject_reason = reject_reason_2
    >>> insufficient_fund_reject_2.action = 'suspend_manual'
    >>> insufficient_fund_reject_2.reject_number = 1
    >>> insufficient_fund_reject_2.journal = journal
    >>> insufficient_fund_reject_2.save()
    >>> journal.reload()

Create Subscriber::

    >>> subscriber = create_party_person()
    >>> subscriber2 = create_party_person(name='other')

Create SEPA mandate::

    >>> subscriber_account = Account()
    >>> subscriber_account.bank = bank
    >>> subscriber_account.owners.append(subscriber)
    >>> subscriber_account.currency = currency
    >>> subscriber_account.number = 'BE82068896274468'
    >>> subscriber_account.save()
    >>> subscriber2_account = Account()
    >>> subscriber2_account.bank = bank2
    >>> subscriber2_account.owners.append(subscriber2)
    >>> subscriber2_account.currency = currency
    >>> subscriber2_account.number = 'FR7630001007941234567890185'
    >>> subscriber2_account.save()
    >>> Mandate = Model.get('account.payment.sepa.mandate')
    >>> mandate = Mandate()
    >>> mandate.company = company
    >>> mandate.party = subscriber
    >>> mandate.account_number = subscriber_account.numbers[0]
    >>> mandate.identification = 'MANDATE'
    >>> mandate.type = 'recurrent'
    >>> mandate.signature_date = datetime.date.today()
    >>> mandate.save()
    >>> mandate.click('request')
    >>> mandate.click('validate_mandate')
    >>> mandate2 = Mandate()
    >>> mandate2.company = company
    >>> mandate2.party = subscriber2
    >>> mandate2.account_number = subscriber2_account.numbers[0]
    >>> mandate2.identification = 'MANDATE 2'
    >>> mandate2.type = 'recurrent'
    >>> mandate2.signature_date = datetime.date.today()
    >>> mandate2.save()
    >>> mandate2.click('request')
    >>> mandate2.click('validate_mandate')

Create Contract::

    >>> BillingMode = Model.get('offered.billing_mode')
    >>> monthly, = BillingMode.find([
    ...         ('code', '=', 'monthly_direct_debit'), ('direct_debit', '=', True)])
    >>> contract_start_date = datetime.date.today()
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> bool(contract.billing_informations.pop(0))
    True
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=monthly,
    ...         payment_term=monthly.allowed_payment_terms[0],
    ...         payer=subscriber,
    ...         direct_debit_day=5,
    ...         sepa_mandate=mandate))
    >>> contract.contract_number = '123456789'
    >>> contract.billing_informations[0].direct_debit_account = \
    ...     mandate.account_number.account
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract2 = Contract()
    >>> contract2.company = company
    >>> contract2.subscriber = subscriber2
    >>> contract2.start_date = contract_start_date
    >>> contract2.product = product
    >>> bool(contract2.billing_informations.pop(0))
    True
    >>> contract2.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=monthly,
    ...         payment_term=monthly.allowed_payment_terms[0],
    ...         payer=subscriber2,
    ...         direct_debit_day=5,
    ...         sepa_mandate=mandate2))
    >>> contract2.contract_number = '123456780'
    >>> contract2.billing_informations[0].direct_debit_account = \
    ...     mandate2.account_number.account
    >>> contract2.save()
    >>> Wizard('contract.activate', models=[contract2]).execute('apply')

Create invoice::

    >>> until_date = contract_start_date + relativedelta(months=1)
    >>> generate_invoice = Wizard('contract.do_invoice', models=[contract])
    >>> generate_invoice.form.up_to_date = until_date
    >>> generate_invoice.execute('invoice')
    >>> contract_invoices = contract.invoices
    >>> len(contract_invoices) == 2
    True
    >>> invoice_no_mandate, invoice = contract_invoices
    >>> generate_invoice2 = Wizard('contract.do_invoice', models=[contract2])
    >>> generate_invoice2.form.up_to_date = until_date
    >>> generate_invoice2.execute('invoice')
    >>> contract_invoices2 = contract2.invoices
    >>> invoice2_no_mandate, invoice2 = contract_invoices2
    >>> invoice.invoice.sepa_mandate = mandate
    >>> invoice2.invoice.sepa_mandate = mandate2
    >>> invoice.invoice.click('post')
    >>> invoice_no_mandate.invoice.click('post')
    >>> invoice_no_mandate.invoice.sepa_mandate = None
    >>> invoice_no_mandate.invoice.save()
    >>> invoice2.invoice.click('post')
    >>> invoice2_no_mandate.invoice.click('post')
    >>> invoice2_no_mandate.invoice.sepa_mandate = None
    >>> invoice2_no_mandate.invoice.save()
    >>> invoice.invoice.sepa_mandate == mandate
    True
    >>> invoice2.invoice.sepa_mandate == mandate2
    True
    >>> invoice_no_mandate.invoice.sepa_mandate is None
    True
    >>> invoice2_no_mandate.invoice.sepa_mandate is None
    True
    >>> lines = [invoice_no_mandate.invoice.lines_to_pay[0],
    ...     invoice2_no_mandate.invoice.lines_to_pay[0]]
    >>> wiz = Wizard('account.payment.payment_information_modification', models=lines)
    >>> wiz.form.new_date = datetime.date.today()
    >>> def check_exception(wiz):
    ...     try:
    ...         wiz.execute('check')
    ...     except Exception:
    ...         return True
    ...     return False
    >>> check_exception(wiz) is True
    True
    >>> lines = list(invoice_no_mandate.invoice.lines_to_pay) + list(
    ...     invoice2.invoice.lines_to_pay)
    >>> wiz = Wizard('account.payment.payment_information_modification', models=lines)
    >>> new_date = datetime.date.today() + relativedelta(months=2)
    >>> wiz.form.new_date = new_date
    >>> wiz.execute('check')
    >>> wiz.execute('process_update_mandate')
    >>> invoice_no_mandate.invoice.reload()
    >>> invoice2.invoice.reload()

 Now the invoice whitout mandate should have the right one::


 And the other invoice must not have been modified::

    >>> invoice_no_mandate.invoice.sepa_mandate == mandate
    True
    >>> invoice_no_mandate.invoice.lines_to_pay[0].payment_date == new_date
    True
    >>> invoice2.invoice.lines_to_pay[0].payment_date == new_date
    True
    >>> invoice2.invoice.sepa_mandate == mandate2
    True
