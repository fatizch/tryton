# encoding: utf-8
import os
import datetime
import psycopg2
import json

from dateutil.relativedelta import relativedelta
from decimal import Decimal

from proteus import config, Model, Wizard
from trytond.exceptions import UserError, UserWarning

from trytond.modules.coog_core.test_framework import switch_user


def parse_environ(name, default):
    if name in os.environ:
        value = os.environ[name]
        if value in ('0', 'FALSE', 'False', 'false'):
            value = False
    else:
        value = default
    return value


_modules_to_ignore = [
    'test',  # Trytond test modules
    'account_per_product',  # Breaks everything
    'endorsement_process',  # To use endorsements without processes
    'endorsement_party_process',  # To use endorsements without processes
    'endorsement_set_process',  # We do not test contract sets so far
    'contract_set',  # We do not test contract sets so far
    'contract_set_insurance_invoice',  # We do not test contract sets so far
    'contract_set_process',  # We do not test contract sets so far
    'endorsement_set',  # We do not test it so far
    'third_party_protocol_almerys',  # Incompatible with bank tests case
    'claim_almerys',  # Requires third_party_protocol_almerys
    ]


DB_USER = parse_environ('PGUSER', 'tryton')
DB_PASSWORD = parse_environ('PGPASSWORD', 'tryton')
DB_HOST = parse_environ('PGHOST', 'localhost')

COOG_USER = parse_environ('GEN_COOG_USER', 'admin')
COOG_PASSWORD = parse_environ('GEN_COOG_PASSWORD', 'admin')

TESTING = parse_environ('GEN_TESTING', False)
COOG_BINARY = parse_environ('GEN_COOG_BINARY', 'coog')
RESTART_SERVER = parse_environ('GEN_RESTART_SERVER', True)

# If CREATE_NEW_DB is True, a database name DB_NAME will be dropped,
# re-created, then initialized with all vailable modules installed
DB_NAME = parse_environ('GEN_DB_NAME', 'generated')
CREATE_NEW_DB = parse_environ('GEN_CREATE_NEW_DB', False)

# If RESTORE_DB is True, the database DB_NAME will be dropped, then re-created
# using RESTOR_FROM as a template
RESTORE_DB = parse_environ('GEN_RESTORE_DB', False)
RESTORE_FROM = parse_environ('GEN_RESTORE_FROM', None)

BASIC_INIT = parse_environ('GEN_BASIC_INIT', True)
LOAD_ZIP_CODES = parse_environ('GEN_LOAD_ZIP_CODES', True)
LOAD_BANKS = parse_environ('GEN_LOAD_BANKS', True)
LOAD_ACCOUNTING = parse_environ('GEN_LOAD_ACCOUNTING', True)
CREATE_PROCESSES = parse_environ('GEN_CREATE_PROCESSES', True)
CREATE_ACTORS = parse_environ('GEN_CREATE_ACTORS', True)
CREATE_PRODUCTS = parse_environ('GEN_CREATE_PRODUCTS', True)
CREATE_COMMISSION_CONFIG = parse_environ(
    'GEN_CREATE_COMMISSION_CONFIG', True)
CREATE_CONTRACTS = parse_environ('GEN_CREATE_CONTRACTS', True)
BILL_CONTRACTS = parse_environ('GEN_BILL_CONTRACTS', True)
CREATE_CLAIMS = parse_environ('GEN_CREATE_CLAIMS', True)
GENERATE_REPORTINGS = parse_environ('GEN_GENERATE_REPORTINGS', True)
TEST_APIS = parse_environ('GEN_TEST_APIS', False)


assert TESTING or (RESTORE_DB and not CREATE_NEW_DB
    or CREATE_NEW_DB and not RESTORE_DB), \
    'Choose between restoring and creating a new database'


def do_print(x):
    if not TESTING:
        print(x)


def assert_eq(x, y):
    assert x == y, 'Assertion error, got %s, expected %s' % (str(x), str(y))


def test_error(error_class, func, *func_args, **func_kwargs):
    try:
        func(*func_args, **func_kwargs)
        raise Exception('Expected error was not raised')
    except error_class:
        pass


do_print('\nDefining constants')  # {{{
_base_date = datetime.date(2000, 1, 1)
_base_contract_date = datetime.date(2018, 1, 1)
_contract_rebill_date = datetime.date(2018, 7, 1)
_contract_rebill_post_date = datetime.date(2018, 6, 1)
_contract_payment_date = datetime.date(2018, 5, 1)
_death_claim_date = datetime.date(2018, 7, 12)
_illness_claim_date = datetime.date(2018, 5, 12)
_illness_claim_end_date_1 = datetime.date(2018, 7, 12)
_illness_claim_end_date_2 = datetime.date(2018, 7, 26)
_commission_invoice_date = datetime.date(2018, 7, 31)
_slip_generation_date = datetime.date(2018, 9, 1)
_account_chart_code = 'PCS'
_default_receivable_code = '4117'
_default_payable_code = '467'
_default_revenue_code = '706'
_default_expense_code = '622'
_lang_code = 'fr'
_currency_code = 'EUR'
_country_code = 'FR'
_company_name = 'Société Coog'
_company_bank_account = 'FR7610107004738784651651383'
_company_bank_bic = 'SOCLFRP1XXX'
_insurer_name = 'Mon assureur'
_broker_name = 'Mon courtier'
_lender_name = 'Mon prêteur'
_test_ibans = [
    'FR4930066718327481116186933',
    'FR4330066818837573839295218',
    'FR2830066672622162315321627',
    'FR5530066542849141338211362',
    'FR0730066972468936615795113',
    'FR9330066812885514771837872',
    'FR9330066812885514771837872',
    'FR3430066753941223588832769',
    'FR0830066832195314724587549',
    'FR2030066378352292545684161',
    'FR2730066897575269427455715',
    'FR2230066446544236999944545',
    'FR0930066987275756646844158',
    'FR1730066246237579312716591',
    'FR4630066476937225464577286',
    'FR8930066999195411969171933',
    'FR0630066874485998598859995',
    'FR8630066373597772548279933',
    'FR5730066717949961591819945',
    ]


def get_iban():
    return _test_ibans.pop()


# }}}

if CREATE_NEW_DB:  # {{{
    TRYTOND_CONFIG = os.environ['TRYTOND_CONFIG']
    assert all([DB_NAME, DB_PASSWORD, DB_USER]), 'DB connection data not set'
    do_print('\nNew database')
    do_print('    Creating new database %s' % DB_NAME)  # {{{

    if RESTART_SERVER:
        os.system('%s server kill' % COOG_BINARY)

    conn = psycopg2.connect(
        "dbname='postgres' user='%s' host='%s' password='%s'" % (
            DB_USER, DB_HOST, DB_PASSWORD))
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("DROP DATABASE %s;" % DB_NAME)
    except psycopg2.ProgrammingError:
        # Database may not exist already
        pass

    cur.execute("CREATE DATABASE %s;" % DB_NAME)
    # }}}

    do_print('    Initializing database')  # {{{
    os.system('echo "%s" > /tmp/trpass' % COOG_PASSWORD)

    os.system('TRYTONPASSFILE=/tmp/trpass trytond-admin -d %s -c %s '
        '--email %s -u ir' % (
            DB_NAME, TRYTOND_CONFIG, 'admin@coopengo.com'))

    os.system('rm /tmp/trpass')

    conn = psycopg2.connect(
        "dbname='%s' user='%s' host='%s' password='%s'" % (
            DB_NAME, DB_USER, DB_HOST, DB_PASSWORD))
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('UPDATE ir_module SET state = \'to activate\' '
        'WHERE name NOT IN (%s);' % (
            ', '.join("'%s'" % x for x in _modules_to_ignore)))
    os.system('TRYTONPASSFILE=/tmp/trpass trytond-admin -d %s -c %s -u ir' % (
            DB_NAME, TRYTOND_CONFIG))

    if RESTART_SERVER:
        os.system('%s server start' % COOG_BINARY)
    # }}}
elif RESTORE_DB:
    assert all([DB_NAME, DB_PASSWORD, DB_USER]), 'DB connection data not set'
    do_print('\nRestoring database')  # {{{

    if RESTART_SERVER:
        os.system('%s server kill' % COOG_BINARY)

    conn = psycopg2.connect(
        "dbname='postgres' user='%s' host='%s' password='%s'" % (
            DB_USER, DB_HOST, DB_PASSWORD))
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("DROP DATABASE %s;" % DB_NAME)
    except psycopg2.ProgrammingError:
        # Database may not exist already
        pass

    cur.execute("CREATE DATABASE %s TEMPLATE %s;" % (DB_NAME, RESTORE_FROM))

    if RESTART_SERVER:
        os.system('%s server start' % COOG_BINARY)
    # }}}
# }}}

do_print('\nConnecting to Coog')  # {{{
if not TESTING:
    assert COOG_USER
    config = config.set_trytond(
        database='postgresql://%s:%s@%s:5432/%s' % (
            DB_USER, DB_PASSWORD, DB_HOST, DB_NAME),
        user=COOG_USER,
        config_file=os.environ['TRYTOND_CONFIG'],
        )
else:
    from trytond.config import config
    config.set('database', 'language', 'fr')
    # Pasrau configuration
    config.add_section('dsn')
    config.set('dsn', 'sender_code', '1')
    config.set('dsn', 'sender_nic', '00029')
    config.set('dsn', 'sender_contact_civility', '01')
    config.set('dsn', 'sender_contact_full_name', 'Admin Coopengo')
    config.set('dsn', 'sender_contact_email', 'admin@coopengo.com')
    config.set('dsn', 'sender_contact_phone', '0101010101')
    config.set('dsn', 'code_apen', '5829C')
    config.set('dsn', 'nic_etablissement', '00029')
    config.set('dsn', 'apet_etablissement', '5829C')
    config.set('dsn', 'fraction_number', '10')

    import trytond.modules as modules
    from trytond.tests.tools import activate_modules

    modules = os.listdir(
        os.path.abspath(os.path.join(modules.__file__, os.path.pardir)))
    modules = [x for x in modules
        if '.' not in x and x not in _modules_to_ignore and x != '__pycache__']
    config = activate_modules(modules, cache_file_name='global_tests')


def run_test_cases(names):  # {{{
    TestCase = Wizard('ir.test_case.run')
    test_cases = [
        x.name for x in TestCaseInstance.find([('method_name', 'in', names)])]
    for case in TestCase.form.test_cases:
        if case.test in test_cases:
            case.selected = True
    TestCase.execute('execute_test_cases')
# }}}


# }}}

do_print('\nFetching models')  # {{{
Account = Model.get('account.account')
AccountConfiguration = Model.get('account.configuration')
AccountKind = Model.get('account.account.type')
AccountProduct = Model.get('product.product')
AccountProductTemplate = Model.get('product.template')
AccountTemplate = Model.get('account.account.template')
AnalyticAccount = Model.get('analytic_account.account')
AverageLoanPremiumRule = Model.get('loan.average_premium_rule')
Benefit = Model.get('benefit')
BenefitEligibilityDecision = Model.get('benefit.eligibility.decision')
BillingMode = Model.get('offered.billing_mode')
Bank = Model.get('bank')
BankAccount = Model.get('bank.account')
Claim = Model.get('claim')
ClaimClosingReason = Model.get('claim.closing_reason')
ClaimConfiguration = Model.get('claim.configuration')
ClaimSubStatus = Model.get('claim.sub_status')
Clause = Model.get('clause')
CommercialProduct = Model.get('distribution.commercial_product')
CommissionAgent = Model.get('commission.agent')
CommissionPlan = Model.get('commission.plan')
CommutationManager = Model.get('table.commutation_manager')
Company = Model.get('company.company')
Contract = Model.get('contract')
Coverage = Model.get('offered.option.description')
CoveredElement = Model.get('contract.covered_element')
CoveredEndReason = Model.get('covered_element.end_reason')
Country = Model.get('country.country')
Currency = Model.get('currency.currency')
DefaultPasrauRate = Model.get('claim.pasrau.default.rate')
DistributionNetwork = Model.get('distribution.network')
Channel = Model.get('distribution.channel')
DocumentDescription = Model.get('document.description')
DunningProcedure = Model.get('account.dunning.procedure')
EventDesc = Model.get('benefit.event.description')
ExtraData = Model.get('extra_data')
ExtraDetails = Model.get('extra_details.configuration')
FiscalYear = Model.get('account.fiscalyear')
Group = Model.get('res.group')
Indemnification = Model.get('claim.indemnification')
Insurer = Model.get('insurer')
Invoice = Model.get('account.invoice')
InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
InvoiceSlipConfiguration = Model.get('account.invoice.slip.configuration')
IrAction = Model.get('ir.action')
IrModel = Model.get('ir.model')
IrUiIcon = Model.get('ir.ui.icon')
ItemDesc = Model.get('offered.item.description')
Journal = Model.get('account.journal')
Lang = Model.get('ir.lang')
Loan = Model.get('loan')
LossDesc = Model.get('benefit.loss.description')
MoveLine = Model.get('account.move.line')
MoveLinePasrauRate = Model.get('account.move.line.pasrau.rate')
NetCalculationRule = Model.get('claim.net_calculation_rule')
Party = Model.get('party.party')
PartyConfiguration = Model.get('party.configuration')
PartyPasrauRate = Model.get('party.pasrau.rate')
Payment = Model.get('account.payment')
PaymentGroup = Model.get('account.payment.group')
PaymentJournal = Model.get('account.payment.journal')
PaymentJournalFailureAction = Model.get(
    'account.payment.journal.failure_action')
PaymentJournalRejectReason = Model.get('account.payment.journal.reject_reason')
PaymentMethod = Model.get('account.invoice.payment.method')
PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
Process = Model.get('process')
ProcessConfiguration = Model.get('process.configuration')
ProcessStep = Model.get('process.step')
ProductCategory = Model.get('product.category')
ProductConfiguration = Model.get('offered.configuration')
Product = Model.get('offered.product')
Questionnaire = Model.get('questionnaire')
Reconciliation = Model.get('account.move.reconciliation')
RuleEngine = Model.get('rule_engine')
RuleEngineContext = Model.get('rule_engine.context')
Sequence = Model.get('ir.sequence')
SequenceStrict = Model.get('ir.sequence.strict')
StatementJournal = Model.get('account.statement.journal')
StatementCancelMotive = Model.get('account.statement.journal.cancel_motive')
Table = Model.get('table')
Tax = Model.get('account.tax')
TestCase = Model.get('ir.test_case')
TestCaseInstance = Model.get('ir.test_case.instance')
UnderwritingDecision = Model.get('underwriting.decision')
UnderwritingRule = Model.get('underwriting.rule')
DSNMessage = Model.get('dsn.message')
User = Model.get('res.user')
Warning = Model.get('res.user.warning')
# }}}

do_print('\nGet currency')  # {{{
try:
    currency, = Currency.find([('code', '=', _currency_code)])
except ValueError:
    # When testing, the currency will not be created when installing the module
    currency = Currency()
    currency.code = _currency_code
    currency.name = _currency_code
    currency.numeric_code = '123'
    currency.symbol = '€'
    currency.rounding = Decimal('0.01')
    currency.digits = 2
    currency.mon_grouping = '[3, 3, 0]'
    currency.mon_decimal_point = ','
    currency.mon_thousands_sep = ' '
    currency.negative_sign = '-'
    currency.save()
# }}}

do_print('\nGet country')  # {{{
try:
    country, = Country.find([('code', '=', _country_code)])
except ValueError:
    # When testing, the country will not be created when installing the module
    country = Country()
    country.code = _country_code
    country.name = _country_code
    country.code3 = _country_code
    country.code_numeric = '123'
    country.save()
# }}}

do_print('\nGet lang')  # {{{
lang, = Lang.find([('code', '=', _lang_code)])
# }}}

if BASIC_INIT:  # {{{
    do_print('\nDatabase initialization')
    do_print('    Cleaning up configuration wizards')  # {{{
    ConfigItem = Model.get('ir.module.config_wizard.item')
    for elem in ConfigItem.find([]):
        elem.state = 'done'
        elem.save()
    # }}}

    do_print('    Setting up test cases')  # {{{
    test_case_config = TestCase(1)
    test_case_config.main_company_name = _company_name
    test_case_config.save()
    # }}}

    do_print('    Creating company')  # {{{
    company_party = Party(
        name=_company_name,
        lang=lang,
        )
    company_party.all_addresses[0].street = "\n\n1 rue d'Hauteville"
    company_party.all_addresses[0].zip = '75004'
    company_party.all_addresses[0].city = 'PARIS'
    company_party.all_addresses[0].country = country
    company_party.save()
    CompanyConfig = Wizard('company.company.config')
    CompanyConfig.execute('company')
    CompanyConfig.form.party = company_party
    CompanyConfig.form.currency = currency
    CompanyConfig.execute('add')
    # }}}

config._context = User.get_preferences(True, {})
config._context['language'] = 'fr'
# }}}

do_print('\nGet Company')  # {{{
company, = Company.find([])
company_party = company.party


def process_next(target):  # {{{
    target.save()
    button = '_button_next_%i' % target.current_state.process.id
    res = getattr(target.__class__._proxy, button)(
        [target.id], config._context)
    target.reload()
    return res
# }}}


def process_previous(target):  # {{{
    target.save()
    button = '_button_previous_%i' % target.current_state.process.id
    res = getattr(target.__class__._proxy, button)(
        [target.id], config._context)
    target.reload()
    return res
# }}}


def get_rule(code):  # {{{
    rule, = RuleEngine.find([('short_name', '=', code)])
    return rule
# }}}


def get_extra_data(code):  # {{{
    extra_data, = ExtraData.find([('name', '=', code)])
    return extra_data


# }}}
# }}}

do_print('\nGet Rule engine context')  # {{{
rule_context = RuleEngineContext(1)
commission_context, = RuleEngineContext.find(
    [('name', '=', 'Commission Context')])
# }}}

if BASIC_INIT:  # {{{
    do_print('\nBasic initialization')
    do_print('    Setting global configuration')  # {{{
    run_test_cases(['set_global_search', 'set_language_translatable'])
    # }}}

    do_print('    Creating users')  # {{{
    run_test_cases(['authorizations_test_case'])
    # }}}

    do_print('    Defining default language for parties')  # {{{
    party_config = PartyConfiguration(1)
    party_config.party_lang = lang
    party_config.save()
    # }}}

    do_print('    Process configuration')  # {{{
    process_config = ProcessConfiguration(1)
    process_config.share_tasks = False
    process_config.save()
    # }}}
# }}}

if LOAD_ZIP_CODES:  # {{{
    do_print('\nLoading zip codes')  # {{{
    ZipCodeLoader = Wizard('country.hexapost.set.wizard')
    ZipCodeLoader.form.use_default = True
    ZipCodeLoader.execute('set_')
    # }}}
# }}}

if LOAD_BANKS:  # {{{
    do_print('\nLoading banks')  # {{{
    BankLoader = Wizard('bank_cog.data.set.wizard')
    BankLoader.form.file_format = 'coog_file'
    BankLoader.form.use_default = True
    BankLoader.execute('set_')
    company_bank_account = BankAccount()
    company_bank_account.currency = currency
    company_bank_account.number = _company_bank_account
    company_bank_account.start_date = None
    company_bank_account.bank = Bank.find([('bic', '=', _company_bank_bic)])[0]
    company_bank_account.owners.append(Party(company_party.id))
    company_bank_account.save()
    # }}}
# }}}

if LOAD_ACCOUNTING:  # {{{
    do_print('\nLoading Accounting')
    do_print('    Creating fiscal years')  # {{{
    base_year = _base_date.year
    for i in range(30):
        name = str(base_year + i)
        post_move_sequence = Sequence(
            name=name, code='account.move', company=company)
        post_move_sequence.save()
        invoice_seq = SequenceStrict(
            name=name, code='account.invoice', company=company)
        invoice_seq.save()
        fiscalyear = FiscalYear(name=name)
        fiscalyear.start_date = datetime.date(base_year + i, 1, 1)
        fiscalyear.end_date = datetime.date(base_year + i, 12, 31)
        fiscalyear.company = company
        fiscalyear.post_move_sequence = post_move_sequence
        fiscalyear.invoice_sequences[0].out_invoice_sequence = invoice_seq
        fiscalyear.invoice_sequences[0].in_invoice_sequence = invoice_seq
        fiscalyear.invoice_sequences[0].out_credit_note_sequence = invoice_seq
        fiscalyear.invoice_sequences[0].in_credit_note_sequence = invoice_seq
        fiscalyear.invoice_sequences[0].company = company
        fiscalyear.save()

        fiscalyear.reload()
        FiscalYear.create_period([fiscalyear.id], config.context)
    # }}}

    do_print('    Creating account chart')  # {{{
    AccountChart = Wizard('account.create_chart')
    AccountChart.execute('account')
    AccountChart.form.company = company
    AccountChart.form.account_template, = AccountTemplate.find([
            ('code', '=', _account_chart_code)])
    AccountChart.execute('create_account')
    AccountChart.form.account_receivable, = Account.find([
            ('code', '=', _default_receivable_code)])
    AccountChart.form.account_payable, = Account.find([
            ('code', '=', _default_payable_code)])
    AccountChart.form.product_account_revenue, = Account.find([
            ('code', '=', _default_revenue_code)])
    AccountChart.form.product_account_expense, = Account.find([
            ('code', '=', _default_expense_code)])
    AccountChart.execute('create_properties')
    # }}}

    do_print('    Configuring default accounts')  # {{{
    receivable, = Account.find([('code', '=', _default_receivable_code)])
    receivable.party_required = True
    receivable.save()
    payable, = Account.find([('code', '=', _default_payable_code)])
    payable.party_required = True
    payable.save()
    # }}}

    do_print('    Creating account kinds')  # {{{
    tax_account_kind = AccountKind()
    tax_account_kind.name = 'Taxes'
    tax_account_kind.company = company
    tax_account_kind.statement = 'balance'
    tax_account_kind.save()
    # }}}

    do_print('    Creating required accounts')  # {{{
    tax_parent = Account.find([('code', '=', '4')])[0]
    tax_root = Account()
    tax_root.company = company
    tax_root.name = 'Taxes'
    tax_root.code = '43'
    tax_root.kind = 'view'
    tax_root.type = tax_account_kind
    tax_root.parent = tax_parent
    tax_root.deferral = False
    tax_root.general_ledger_balance = False
    tax_root.party_required = False
    tax_root.reconcile = False
    tax_root.template = tax_parent.template
    tax_root.save()

    def create_tax_account(name, code):
        account = Account()
        account.company = company
        account.name = name
        account.code = code
        account.template = tax_root.template
        account.parent = tax_root
        account.type = tax_root.type
        account.save()
        return account

    csg_tax_account = create_tax_account('Compte CSG', '43000001')
    csg_deductible_tax_account = create_tax_account('Compte CSG déductible',
        '43000002')
    crds_tax_account = create_tax_account('Compte CRDS', '43000003')
    pasrau_tax_account = create_tax_account('Compte Pasrau', '43000004')

    bank_root = Account.find([('code', '=', '512')])[0]
    bank_account = Account()
    bank_account.company = company
    bank_account.name = 'Compte de banque 1'
    bank_account.code = '51200001'
    bank_account.kind = 'other'
    bank_account.type = bank_root.type
    bank_account.parent = bank_root
    bank_account.deferral = True
    bank_account.general_ledger_balance = False
    bank_account.party_required = False
    bank_account.reconcile = False
    bank_account.template = bank_root.template
    bank_account.save()

    loss_root = Account.find([('code', '=', '6')])[0]

    loss_account = Account()
    loss_account.company = company
    loss_account.name = 'Pertes'
    loss_account.code = '67'
    loss_account.template = loss_root.template
    loss_account.parent = loss_root
    loss_account.type = loss_root.type
    loss_account.deferral = True
    loss_account.general_ledger_balance = False
    loss_account.party_required = False
    loss_account.reconcile = False
    loss_account.save()

    exceptional_loss_account = Account()
    exceptional_loss_account.company = company
    exceptional_loss_account.name = 'Pertes Exceptionnelles'
    exceptional_loss_account.code = '67000001'
    exceptional_loss_account.template = loss_account.template
    exceptional_loss_account.parent = loss_account
    exceptional_loss_account.kind = 'expense'
    exceptional_loss_account.type = Account.find(
        [('code', '=', '622')])[0].type
    exceptional_loss_account.deferral = True
    exceptional_loss_account.general_ledger_balance = False
    exceptional_loss_account.party_required = False
    exceptional_loss_account.reconcile = False
    exceptional_loss_account.save()

    exceptional_revenue_root = Account.find([('code', '=', '77')])[0]
    exceptional_revenue_account = Account()
    exceptional_revenue_account.company = company
    exceptional_revenue_account.name = 'Produits exceptionnels'
    exceptional_revenue_account.code = '77000001'
    exceptional_revenue_account.template = exceptional_revenue_root.template
    exceptional_revenue_account.type = Account.find(
        [('code', '=', '7718')])[0].type
    exceptional_revenue_account.parent = exceptional_revenue_root
    exceptional_revenue_account.kind = 'revenue'
    exceptional_revenue_account.deferral = True
    exceptional_revenue_account.general_ledger_balance = False
    exceptional_revenue_account.party_required = False
    exceptional_revenue_account.reconcile = False
    exceptional_revenue_account.save()

    claim_root = Account.find([('code', '=', '622')])[0]
    claim_account = Account()
    claim_account.company = company
    claim_account.name = 'Compte de sinistres'
    claim_account.code = '62200001'
    claim_account.kind = 'other'
    claim_account.type = claim_root.type
    claim_account.parent = claim_root
    claim_account.deferral = True
    claim_account.general_ledger_balance = False
    claim_account.party_required = False
    claim_account.reconcile = False
    claim_account.template = claim_root.template
    claim_account.save()
    # }}}

    do_print('    Creating Taxes')  # {{{
    crds_tax = Tax()
    crds_tax.name = 'CRDS'
    crds_tax.type = 'percentage'
    crds_tax.description = 'Contribution à la réduction de la dette sociale'
    crds_tax.rate = Decimal('-0.005')
    crds_tax.company = company
    crds_tax.invoice_account = crds_tax_account
    crds_tax.credit_note_account = crds_tax_account
    crds_tax.sequence = 1
    crds_tax.save()

    csg_tax = Tax()
    csg_tax.name = 'CSG'
    csg_tax.type = 'percentage'
    csg_tax.description = 'Contribution sociale généralisée'
    csg_tax.rate = Decimal('-0.062')
    csg_tax.company = company
    csg_tax.invoice_account = csg_tax_account
    csg_tax.credit_note_account = csg_tax_account
    csg_tax.sequence = 2
    csg_tax.save()

    csg_deductible_tax = Tax()
    csg_deductible_tax.name = 'CSG déductible'
    csg_deductible_tax.type = 'percentage'
    csg_deductible_tax.description = \
        'Contribution sociale généralisée (déductible)'
    csg_deductible_tax.rate = Decimal('-0.038')
    csg_deductible_tax.company = company
    csg_deductible_tax.invoice_account = csg_deductible_tax_account
    csg_deductible_tax.credit_note_account = csg_deductible_tax_account
    csg_deductible_tax.sequence = 2
    csg_deductible_tax.update_unit_price = True
    csg_deductible_tax.save()

    pasrau_tax = Tax()
    pasrau_tax.name = 'pasrau'
    pasrau_tax.type = 'pasrau_rate'
    pasrau_tax.description = 'Prélèvement à la source (Pasrau)'
    pasrau_tax.company = company
    pasrau_tax.invoice_account = pasrau_tax_account
    pasrau_tax.credit_note_account = pasrau_tax_account
    pasrau_tax.sequence = 3
    pasrau_tax.save()
    # }}}

    do_print('    Creating Accounting catgeories')  # {{{
    insurer_account_category = ProductCategory()
    insurer_account_category.name = 'Insurer Account Category'
    insurer_account_category.code = 'insurer_account_category'
    insurer_account_category.accounting = True
    insurer_account_category.account_expense, = Account.find(
        [('code', '=', '622')])
    insurer_account_category.account_revenue, = Account.find(
        [('code', '=', '706')])
    insurer_account_category.save()

    broker_account_category = ProductCategory()
    broker_account_category.name = 'Broker Account Category'
    broker_account_category.code = 'broker_account_category'
    broker_account_category.accounting = True
    broker_account_category.account_expense, = Account.find(
        [('code', '=', '622')])
    broker_account_category.account_revenue, = Account.find(
        [('code', '=', '706')])
    broker_account_category.save()

    claim_wo_taxes_account_category = ProductCategory()
    claim_wo_taxes_account_category.name = 'Claim (No taxes) Account Category'
    claim_wo_taxes_account_category.code = 'claim_wo_taxes_account_category'
    claim_wo_taxes_account_category.accounting = True
    claim_wo_taxes_account_category.account_expense, = Account.find(
        [('code', '=', '62200001')])
    claim_wo_taxes_account_category.account_revenue, = Account.find(
        [('code', '=', '706')])
    claim_wo_taxes_account_category.save()

    claim_full_taxes_account_category = ProductCategory()
    claim_full_taxes_account_category.name = \
        'Claim (Full taxes) Account Category'
    claim_full_taxes_account_category.code = \
        'claim_full_taxes_account_category'
    claim_full_taxes_account_category.accounting = True
    claim_full_taxes_account_category.account_expense, = Account.find(
        [('code', '=', '62200001')])
    claim_full_taxes_account_category.account_revenue, = Account.find(
        [('code', '=', '706')])
    claim_full_taxes_account_category.supplier_taxes.append(
        Tax(crds_tax.id))
    claim_full_taxes_account_category.supplier_taxes.append(
        Tax(csg_tax.id))
    claim_full_taxes_account_category.supplier_taxes.append(
        Tax(pasrau_tax.id))
    claim_full_taxes_account_category.save()

    claim_reduced_taxes_account_category = ProductCategory()
    claim_reduced_taxes_account_category.name = \
        'Claim (Reduced taxes) Account Category'
    claim_reduced_taxes_account_category.code = \
        'claim_reduced_taxes_account_category'
    claim_reduced_taxes_account_category.accounting = True
    claim_reduced_taxes_account_category.account_expense, = Account.find(
        [('code', '=', '62200001')])
    claim_reduced_taxes_account_category.account_revenue, = Account.find(
        [('code', '=', '706')])
    claim_reduced_taxes_account_category.supplier_taxes.append(
        Tax(crds_tax.id))
    claim_reduced_taxes_account_category.supplier_taxes.append(
        Tax(csg_deductible_tax.id))
    claim_reduced_taxes_account_category.supplier_taxes.append(
        Tax(pasrau_tax.id))
    claim_reduced_taxes_account_category.save()
    # }}}

    do_print('    Creating Accounting products templates')  # {{{
    insurer_account_product_template = AccountProductTemplate()
    insurer_account_product_template.name = 'Chargement Produit'
    insurer_account_product_template.type = 'service'
    insurer_account_product_template.cost_price = Decimal(1)
    insurer_account_product_template.list_price = Decimal(1)
    insurer_account_product_template.account_category = \
        insurer_account_category
    insurer_account_product_template.products[0].code = 'chargement_produit'
    insurer_account_product_template.save()
    insurer_account_product = insurer_account_product_template.products[0]

    broker_account_product_template = AccountProductTemplate()
    broker_account_product_template.name = 'Commissions Courtier'
    broker_account_product_template.type = 'service'
    broker_account_product_template.cost_price = Decimal(1)
    broker_account_product_template.list_price = Decimal(1)
    broker_account_product_template.account_category = broker_account_category
    broker_account_product_template.products[0].code = 'commission_courtier'
    broker_account_product_template.save()
    broker_account_product = broker_account_product_template.products[0]

    claim_product_template_no_taxes = AccountProductTemplate()
    claim_product_template_no_taxes.name = 'Règlements sinistres'
    claim_product_template_no_taxes.type = 'service'
    claim_product_template_no_taxes.cost_price = Decimal(1)
    claim_product_template_no_taxes.list_price = Decimal(1)
    claim_product_template_no_taxes.account_category = \
        claim_wo_taxes_account_category
    claim_product_template_no_taxes.products[0].code = 'reglement_sinistres'
    claim_product_template_no_taxes.save()

    claim_product_template_full_taxes = AccountProductTemplate()
    claim_product_template_full_taxes.name = 'Règlements sinistres (taxes)'
    claim_product_template_full_taxes.type = 'service'
    claim_product_template_full_taxes.cost_price = Decimal(1)
    claim_product_template_full_taxes.list_price = Decimal(1)
    claim_product_template_full_taxes.account_category = \
        claim_full_taxes_account_category
    claim_product_template_full_taxes.products[0].code = \
        'reglement_sinistres_taxes'
    claim_product_template_full_taxes.save()

    claim_product_template_reduced_taxes = AccountProductTemplate()
    claim_product_template_reduced_taxes.name = \
        'Règlements sinistres (taxes réduites)'
    claim_product_template_reduced_taxes.type = 'service'
    claim_product_template_reduced_taxes.cost_price = Decimal(1)
    claim_product_template_reduced_taxes.list_price = Decimal(1)
    claim_product_template_reduced_taxes.account_category = \
        claim_reduced_taxes_account_category
    claim_product_template_reduced_taxes.products[0].code = \
        'reglement_sinistres_taxes_reduites'
    claim_product_template_reduced_taxes.save()
    # }}}

    do_print('    Creating Journals')  # {{{
    bank_journal = Journal()
    bank_journal.company = company
    bank_journal.name = 'Banque'
    bank_journal.code = 'BANK'
    bank_journal.type = 'statement'
    bank_journal.debit_account = bank_account
    bank_journal.credit_account = bank_account
    bank_journal.aggregate = True
    bank_journal.aggregate_posting_behavior = 'except_payment_cancel'
    bank_journal.sequence, = Sequence.find([('code', '=', 'account.journal')])
    bank_journal.save()

    exceptional_journal = Journal()
    exceptional_journal.company = company
    exceptional_journal.name = 'Exceptionnel'
    exceptional_journal.code = 'EXCEPTIONAL'
    exceptional_journal.type = 'write-off'
    exceptional_journal.debit_account = exceptional_loss_account
    exceptional_journal.credit_account = exceptional_revenue_account
    exceptional_journal.sequence, = Sequence.find(
        [('code', '=', 'account.journal')])
    exceptional_journal.save()

    benefit_journal = Journal()
    benefit_journal.company = company
    benefit_journal.name = 'Journal de prestation assureur'
    benefit_journal.code = 'journal_presta_assureur'
    benefit_journal.type = 'claim_insurer_slip'
    benefit_journal.sequence, = Sequence.find(
        [('code', '=', 'account.journal')])
    benefit_journal.save()
    # }}}

    do_print('    Creating Payment method for cash')  # {{{
    payment_method = PaymentMethod()
    payment_method.name = 'Cash'
    payment_method.journal, = Journal.find([('code', '=', 'CASH')])
    payment_method.credit_account = bank_account
    payment_method.debit_account = bank_account
    payment_method.save()
    # }}}

    do_print('    Creating Payment Journals')  # {{{
    payment_manual = PaymentJournal()
    payment_manual.company = company
    payment_manual.name = 'Manuel'
    payment_manual.currency = currency
    payment_manual.process_method = 'manual'
    payment_manual.clearing_account = bank_account
    payment_manual.clearing_journal = bank_journal
    payment_manual.post_clearing_move = True
    payment_manual.always_create_clearing_move = True
    payment_manual.save()

    sepa_reject_reasons = {
        x.code: x
        for x in PaymentJournalRejectReason.find(
            [('code', 'in', ['AC01', 'AC06', 'AM04'])])}
    payment_sepa = PaymentJournal()
    payment_sepa.company = company
    payment_sepa.name = 'Sepa'
    payment_sepa.currency = currency
    payment_sepa.process_method = 'sepa'
    payment_sepa.clearing_account = bank_account
    payment_sepa.clearing_journal = bank_journal
    payment_sepa.post_clearing_move = True
    payment_sepa.always_create_clearing_move = True
    payment_sepa.sepa_bank_account_number = company.party.bank_accounts[0]
    payment_sepa.sepa_receivable_flavor = 'pain.008.001.02'
    payment_sepa.sepa_payable_flavor = 'pain.001.001.03'
    action = payment_sepa.failure_actions.new()
    action.reject_reason = sepa_reject_reasons['AC01']
    action.action = 'suspend'
    action = payment_sepa.failure_actions.new()
    action.reject_reason = sepa_reject_reasons['AC06']
    action.action = 'manual'
    action = payment_sepa.failure_actions.new()
    action.reject_reason = sepa_reject_reasons['AM04']
    action.action = 'retry'
    payment_sepa.save()

    payable_reject_reason = PaymentJournalRejectReason()
    payable_reject_reason.code = 'ALL'
    payable_reject_reason.payment_kind = 'payable'
    payable_reject_reason.process_method = 'sepa'
    payable_reject_reason.description = 'Coog Generic Reject Reason'
    payable_reject_reason.save()
    # }}}

    do_print('    Creating Statement Journals')  # {{{
    cheque_sequence = Sequence(
        name='Numéros de chèques', code='statement', company=company)
    cheque_sequence.save()

    cheque_journal_cancel_motive = StatementCancelMotive()
    cheque_journal_cancel_motive.name = 'Compte vide'
    cheque_journal_cancel_motive.code = 'empty_account'
    cheque_journal_cancel_motive.save()

    cheque_journal = StatementJournal()
    cheque_journal.name = 'Chèque'
    cheque_journal.code = 'cheque'
    cheque_journal.currency = currency
    cheque_journal.company = company
    cheque_journal.journal = bank_journal
    cheque_journal.bank_account = company.party.bank_accounts[0]
    cheque_journal.account = bank_account
    cheque_journal.process_method = 'cheque'
    cheque_journal.sequence = cheque_sequence
    cheque_journal.cancel_motives.append(cheque_journal_cancel_motive)
    cheque_journal.save()
    # }}}

    do_print('    Creating payment terms')  # {{{
    payment_term = PaymentTerm()
    payment_term.name = 'Par défaut'
    payment_term.lines.append(PaymentTermLine())
    payment_term.save()
    # }}}

    do_print('    Creating billing modes')  # {{{
    freq_monthly = BillingMode()
    freq_monthly.name = 'Mensuel (manuel)'
    freq_monthly.code = 'monthly_manual'
    freq_monthly.frequency = 'monthly'
    freq_monthly.allowed_payment_terms.append(payment_term)
    freq_monthly.save()

    freq_quarterly = BillingMode()
    freq_quarterly.name = 'Trimestriel (manuel)'
    freq_quarterly.code = 'quarterly_manual'
    freq_quarterly.frequency = 'quarterly'
    freq_quarterly.allowed_payment_terms.append(PaymentTerm(payment_term.id))
    freq_quarterly.save()

    freq_half_yearly = BillingMode()
    freq_half_yearly.name = 'Semestriel (manuel)'
    freq_half_yearly.code = 'half_yearly_manual'
    freq_half_yearly.frequency = 'half_yearly'
    freq_half_yearly.allowed_payment_terms.append(PaymentTerm(payment_term.id))
    freq_half_yearly.save()

    freq_yearly = BillingMode()
    freq_yearly.name = 'Annuel (manuel)'
    freq_yearly.code = 'yearly_manual'
    freq_yearly.frequency = 'yearly'
    freq_yearly.allowed_payment_terms.append(PaymentTerm(payment_term.id))
    freq_yearly.save()

    freq_monthly_sepa = BillingMode()
    freq_monthly_sepa.name = 'Mensuel (sepa)'
    freq_monthly_sepa.code = 'monthly_sepa'
    freq_monthly_sepa.frequency = 'monthly'
    freq_monthly_sepa.direct_debit = True
    freq_monthly_sepa.sync_day = '1'
    freq_monthly_sepa.allowed_payment_terms.append(
        PaymentTerm(payment_term.id))
    freq_monthly_sepa.save()

    freq_quarterly_sepa = BillingMode()
    freq_quarterly_sepa.name = 'Trimestriel (sepa)'
    freq_quarterly_sepa.code = 'quarterly_sepa'
    freq_quarterly_sepa.frequency = 'quarterly'
    freq_quarterly_sepa.direct_debit = True
    freq_quarterly_sepa.sync_day = '1'
    freq_quarterly_sepa.sync_month = '1'
    freq_quarterly_sepa.allowed_payment_terms.append(
        PaymentTerm(payment_term.id))
    freq_quarterly_sepa.save()

    freq_half_yearly_sepa = BillingMode()
    freq_half_yearly_sepa.name = 'Semestriel (sepa)'
    freq_half_yearly_sepa.code = 'half_yearly_sepa'
    freq_half_yearly_sepa.frequency = 'half_yearly'
    freq_half_yearly_sepa.direct_debit = True
    freq_half_yearly_sepa.sync_day = '1'
    freq_half_yearly_sepa.sync_month = '1'
    freq_half_yearly_sepa.allowed_payment_terms.append(
        PaymentTerm(payment_term.id))
    freq_half_yearly_sepa.save()

    freq_yearly_sepa = BillingMode()
    freq_yearly_sepa.name = 'Annuel (sepa)'
    freq_yearly_sepa.code = 'yearly_sepa'
    freq_yearly_sepa.frequency = 'yearly'
    freq_yearly_sepa.direct_debit = True
    freq_yearly_sepa.allowed_payment_terms.append(
        PaymentTerm(payment_term.id))
    freq_yearly_sepa.save()
    # }}}

    do_print('    Creating taxes')  # {{{
    # }}}

    do_print('    Creating sepa sequence')  # {{{
    sepa_mandate_sequence = Sequence(
        name='Mandats Sepa', code='account.payment.sepa.mandate',
        company=company)
    sepa_mandate_sequence.save()
    # }}}

    do_print('    Creating analytic accounts')  # {{{
    analytic_root = AnalyticAccount()
    analytic_root.name = 'Racine analytique'
    analytic_root.code = 'analytic_root'
    analytic_root.type = 'root'
    analytic_root.state = 'opened'
    analytic_root.save()

    analytic_child = AnalyticAccount()
    analytic_child.name = 'Éclatement par détails'
    analytic_child.code = 'analytic_child'
    analytic_child.type = 'distribution_over_extra_details'
    analytic_child.state = 'opened'
    analytic_child.parent = analytic_root
    analytic_child.root = analytic_root
    analytic_child.pattern, = ExtraDetails.find([
            ('model_name', '=', 'analytic_account.line')])
    analytic_child.save()
    # }}}

    do_print('    Global accounting configuration')  # {{{
    account_configuration = AccountConfiguration(1)
    account_configuration.sepa_mandate_sequence = sepa_mandate_sequence
    account_configuration.direct_debit_journal = payment_sepa
    account_configuration.broker_bank_transfer_journal = payment_sepa
    account_configuration.broker_check_journal = payment_manual
    account_configuration.commission_invoice_payment_term = payment_term
    account_configuration.insurer_invoice_payment_term = payment_term
    account_configuration.insurer_manual_payment_journal = payment_manual
    account_configuration.insurer_payment_journal = payment_sepa
    account_configuration.default_customer_payment_term = payment_term
    account_configuration.default_dunning_procedure, = DunningProcedure.find(
        [('code', '=', 'french_default_dunning_procedure')])
    account_configuration.surrender_journal, = Journal.find(
        [('code', '=', 'CLAIM')])
    account_configuration.surrender_payment_term = payment_term
    account_configuration.broker_analytic_account_to_use = analytic_child
    account_configuration.save()
    # }}}
# }}}

if CREATE_PROCESSES:  # {{{
    do_print('\nCreating process rules')  # {{{
    claim_info_step_validation = RuleEngine()
    claim_info_step_validation.context = rule_context
    claim_info_step_validation.name = 'Validation de la saisie du préjudice'
    claim_info_step_validation.short_name = 'validation_saisie_prejudice'
    claim_info_step_validation.status = 'validated'
    claim_info_step_validation.type_ = 'process_check'
    claim_info_step_validation.algorithm = '''
if not date_de_debut_du_prejudice():
    ajouter_erreur(u"La date du préjudice n'est pas definie")
if not champs_technique('loss.covered_person.id'):
    ajouter_erreur(u"La personne assurée n'est pas definie")
'''
    claim_info_step_validation.save()
    # }}}

    do_print('\nCreating process steps')
    do_print('    Creating subscriber step')  # {{{
    step_subscriber = ProcessStep()
    step_subscriber.fancy_name = 'Adhérent'
    step_subscriber.technical_name = 'adherent'
    step_subscriber.button_domain = "[('subscriber', '!=', None)]"
    step_subscriber.main_model, = IrModel.find([('model', '=', 'contract')])
    step_subscriber.step_xml = '''
<button name="button_change_start_date" string="Change start date"/>
<group name="broker" colspan="4">
    <label name="broker"/>
    <field name="broker"/>
    <label name="agent"/>
    <field name="agent" widget="selection"/>
    <label name="dist_network"/>
    <field name="dist_network"/>
</group>
<field name="subscriber_desc" widget="richtext" colspan="4"/>
<field name="billing_informations" invisible="1" colspan="4"/>
'''
    step_subscriber.code_after.new()
    step_subscriber.code_after[0].content = 'method'
    step_subscriber.code_after[0].technical_kind = 'step_after'
    step_subscriber.code_after[0].method_name = 'init_first_covered_elements'
    step_subscriber.save()
    # }}}

    do_print('    Creating step adherent prevoyance')  # {{{
    step_life_subscriber = ProcessStep()
    step_life_subscriber.fancy_name = 'Adhérent'
    step_life_subscriber.technical_name = 'adherent_prevoyance'
    step_life_subscriber.button_domain = "[('subscriber', '!=', None)]"
    step_life_subscriber.main_model, = IrModel.find(
        [('model', '=', 'contract')])
    step_life_subscriber.step_xml = '''
<button name="button_change_start_date" string="Change start date"/>
<group name="broker" colspan="4">
    <label name="broker"/>
    <field name="broker"/>
    <label name="agent"/>
    <field name="agent" widget="selection"/>
    <label name="dist_network"/>
    <field name="dist_network"/>
</group>
<field name="subscriber_desc" widget="richtext" colspan="4"/>
<field name="billing_informations" invisible="1" colspan="4"/>
'''
    step_life_subscriber.code_after.new()
    step_life_subscriber.code_after[0].content = 'method'
    step_life_subscriber.code_after[0].technical_kind = 'step_after'
    step_life_subscriber.code_after[0].method_name = \
        'set_subscriber_as_covered_element'
    step_life_subscriber.save()
    # }}}

    do_print('    Creating step risques')  # {{{
    step_covered = ProcessStep()
    step_covered.fancy_name = 'Risques'
    step_covered.technical_name = 'risques'
    step_covered.button_domain = "[]"
    step_covered.main_model, = IrModel.find([('model', '=', 'contract')])
    step_covered.step_xml = '''
<field name="covered_elements" colspan="4" mode="form,tree"
    view_ids="contract_insurance.covered_element_simple_view_form,contract_insurance.covered_element_view_tree"
    yfill="1" yexpand="1"/>
<newline/>
<field name="extra_data_values" no_command="1" colspan="4"/>
'''
    step_covered.code_after.new()
    step_covered.code_after[0].content = 'method'
    step_covered.code_after[0].technical_kind = 'step_after'
    step_covered.code_after[0].method_name = 'check_contract_extra_data'
    step_covered.code_after.new()
    step_covered.code_after[1].content = 'method'
    step_covered.code_after[1].technical_kind = 'step_after'
    step_covered.code_after[1].method_name = 'check_covered_element_extra_data'
    step_covered.save()
    # }}}

    do_print('    Creating step prets')  # {{{
    step_covered_loan = ProcessStep()
    step_covered_loan.fancy_name = 'Risques / Prêts'
    step_covered_loan.technical_name = 'risques_emprunteur'
    step_covered_loan.button_domain = "[]"
    step_covered_loan.main_model, = IrModel.find([('model', '=', 'contract')])
    step_covered_loan.step_xml = '''
<field name="covered_elements" colspan="4" mode="form,tree"
    view_ids="contract_insurance.covered_element_simple_view_form,contract_insurance.covered_element_view_tree"
    yfill="1" yexpand="1"/>
<newline/>
<field name="extra_data_values" no_command="1" colspan="4"/>
<field name="loans" view_ids="loan.ordered_loan_view_list,loan.loan_view_form"
    colspan="4"/>
'''
    step_covered_loan.code_after.new()
    step_covered_loan.code_after[0].content = 'method'
    step_covered_loan.code_after[0].technical_kind = 'step_after'
    step_covered_loan.code_after[0].method_name = 'check_contract_extra_data'
    step_covered_loan.code_after.new()
    step_covered_loan.code_after[1].content = 'method'
    step_covered_loan.code_after[1].technical_kind = 'step_after'
    step_covered_loan.code_after[1].method_name = 'check_contract_loans'
    step_covered_loan.code_after.new()
    step_covered_loan.code_after[2].content = 'method'
    step_covered_loan.code_after[2].technical_kind = 'step_after'
    step_covered_loan.code_after[2].method_name = 'calculate'
    step_covered_loan.code_after.new()
    step_covered_loan.code_after[3].content = 'method'
    step_covered_loan.code_after[3].technical_kind = 'step_after'
    step_covered_loan.code_after[3].method_name = \
        'check_covered_element_extra_data'
    step_covered_loan.code_after.new()
    step_covered_loan.code_after[4].content = 'method'
    step_covered_loan.code_after[4].technical_kind = 'step_after'
    step_covered_loan.code_after[4].method_name = 'check_loan_dates'
    step_covered_loan.save()
    # }}}

    do_print('    Creating step garanties')  # {{{
    step_options = ProcessStep()
    step_options.fancy_name = 'Garanties'
    step_options.technical_name = 'garanties'
    step_options.button_domain = "[]"
    step_options.main_model, = IrModel.find([('model', '=', 'contract')])
    step_options.step_xml = '''
<group id="covered_elements" yfill="1" yexpand="1" colspan="4">
    <hpaned id="covered_element" position="200">
        <child id="tree">
            <button name="option_subscription" string="Gérer les options"/>
            <newline/>
            <field name="multi_mixed_view" group="multi_mixed_view" mode="tree"
                view_ids="contract_insurance.covered_elements_clean_tree"
                expand_toolbar="0" colspan="2"/>
        </child>
        <child id="form">
            <field name="multi_mixed_view" group="multi_mixed_view" mode="form"
                relation="contract.covered_element" relation_field="contract"
                view_ids="contract_insurance.covered_element_simple_view_form"
                expand_toolbar="0"/>
            <field name="multi_mixed_view" group="multi_mixed_view" mode="form"
                relation="contract.option" relation_field="covered_element"
                view_ids="contract.option_view_form" expand_toolbar="0"/>
        </child>
    </hpaned>
</group>
'''
    step_options.code_after.new()
    step_options.code_after[0].content = 'method'
    step_options.code_after[0].technical_kind = 'step_after'
    step_options.code_after[0].method_name = \
        'check_covered_element_option_extra_data'
    step_options.code_after.new()
    step_options.code_after[1].content = 'method'
    step_options.code_after[1].technical_kind = 'step_after'
    step_options.code_after[1].method_name = 'check_at_least_one_covered'
    step_options.code_after.new()
    step_options.code_after[2].content = 'method'
    step_options.code_after[2].technical_kind = 'step_after'
    step_options.code_after[2].method_name = 'calculate'
    step_options.save()
    # }}}

    do_print('    Creating step garanties (loan)')  # {{{
    step_options_loan = ProcessStep()
    step_options_loan.fancy_name = 'Garanties'
    step_options_loan.technical_name = 'garanties_emprunteur'
    step_options_loan.button_domain = "[]"
    step_options_loan.main_model, = IrModel.find([('model', '=', 'contract')])
    step_options_loan.step_xml = '''
<group id="covered_elements" yfill="1" yexpand="1" colspan="4">
    <hpaned id="covered_element" position="200">
        <child id="tree">
            <button name="option_subscription" string="Gérer les options"/>
            <button name="create_extra_premium" string="Majo / Mino"/>
            <newline/>
            <field name="multi_mixed_view" group="multi_mixed_view"
                mode="tree"
                view_ids="contract_insurance.covered_elements_clean_tree"
                expand_toolbar="0" colspan="2"/>
        </child>
        <child id="form">
            <field name="multi_mixed_view" group="multi_mixed_view" mode="form"
                relation="contract.covered_element" relation_field="contract"
                view_ids="contract_insurance.covered_element_simple_view_form"
                expand_toolbar="0"/>
            <field name="multi_mixed_view" group="multi_mixed_view" mode="form"
                relation="contract.option" relation_field="covered_element"
                view_ids="contract.option_view_form" expand_toolbar="0"/>
            <field name="multi_mixed_view" group="multi_mixed_view" mode="form"
                relation="loan.share" relation_field="option"
                view_ids="loan.loan_share_view_form" expand_toolbar="0"/>
        </child>
    </hpaned>
</group>
'''
    step_options_loan.code_after.new()
    step_options_loan.code_after[0].content = 'method'
    step_options_loan.code_after[0].technical_kind = 'step_after'
    step_options_loan.code_after[0].method_name = \
        'check_covered_element_option_extra_data'
    step_options_loan.code_after.new()
    step_options_loan.code_after[1].content = 'method'
    step_options_loan.code_after[1].technical_kind = 'step_after'
    step_options_loan.code_after[1].method_name = 'check_at_least_one_covered'
    step_options_loan.code_after.new()
    step_options_loan.code_after[2].content = 'method'
    step_options_loan.code_after[2].technical_kind = 'step_after'
    step_options_loan.code_after[2].method_name = 'check_options_dates'
    step_options_loan.code_after.new()
    step_options_loan.code_after[3].content = 'method'
    step_options_loan.code_after[3].technical_kind = 'step_after'
    step_options_loan.code_after[3].method_name = \
        'check_no_option_without_loan'
    step_options_loan.code_after.new()
    step_options_loan.code_after[4].content = 'method'
    step_options_loan.code_after[4].technical_kind = 'step_after'
    step_options_loan.code_after[4].method_name = \
        'check_no_loan_without_option'
    step_options_loan.code_after.new()
    step_options_loan.code_after[5].content = 'method'
    step_options_loan.code_after[5].technical_kind = 'step_after'
    step_options_loan.code_after[5].method_name = 'calculate'
    step_options_loan.save()
    # }}}

    do_print('    Creating step required documents')  # {{{
    step_documents = ProcessStep()
    step_documents.fancy_name = 'Documents'
    step_documents.technical_name = 'documents'
    step_documents.button_domain = "[]"
    step_documents.main_model, = IrModel.find([('model', '=', 'contract')])
    step_documents.step_xml = '''
<field name='document_request_lines' colspan="4"/>
'''
    step_documents.code_before.new()
    step_documents.code_before[0].content = 'method'
    step_documents.code_before[0].technical_kind = 'step_before'
    step_documents.code_before[0].method_name = \
        'init_subscription_document_request'
    step_documents.code_after.new()
    step_documents.code_after[0].content = 'method'
    step_documents.code_after[0].technical_kind = 'step_after'
    step_documents.code_after[0].method_name = 'check_required_documents'
    step_documents.code_after[0].parameters = 'True'
    step_documents.save()
    # }}}

    do_print('    Creating step contract underwriting')  # {{{
    step_underwriting = ProcessStep()
    step_underwriting.fancy_name = 'Analyse de risques'
    step_underwriting.technical_name = 'underwriting'
    step_underwriting.button_domain = "[]"
    step_underwriting.main_model, = IrModel.find([('model', '=', 'contract')])
    step_underwriting.step_xml = '''
<field name="document_request_lines" colspan="4"/>
<field name='underwritings' mode="form" expand_toolbar="1" colspan="4"/>
<newline/>
<group id="underwriting_buttons" colspan="4" yfill="1" yexpand="0">
    <button name="button_decline" string="Décliner" icon="cancel-list"/>
    <button name="create_extra_premium" string="Surprimes"
        icon="tryton-currency"/>
    <button name="propagate_exclusions" string="Exclusions"
        icon="cancel-list"/>
</group>
'''
    step_underwriting.code_before.new()
    step_underwriting.code_before[-1].content = 'method'
    step_underwriting.code_before[-1].technical_kind = 'step_before'
    step_underwriting.code_before[-1].method_name = 'update_underwritings'
    step_underwriting.code_after.new()
    step_underwriting.code_after[-1].content = 'method'
    step_underwriting.code_after[-1].technical_kind = 'step_after'
    step_underwriting.code_after[-1].method_name = 'check_underwriting_complete'
    step_underwriting.authorizations.append(
        Group.find([('xml_id', '=',
                    'contract_underwriting.group_contract_underwriting')])[0])
    step_underwriting.save()
    # }}}

    do_print('    Creating step paiement')  # {{{
    step_payment = ProcessStep()
    step_payment.fancy_name = 'Paiement'
    step_payment.technical_name = 'paiement'
    step_payment.button_domain = "[]"
    step_payment.main_model, = IrModel.find([('model', '=', 'contract')])
    step_payment.step_xml = '''
<field name="billing_informations" mode="form"
    view_ids="_extra_views.step_paiement_billing_information_form"
    expand_toolbar="0" yfill="1"/>
<newline/>
<field name="fees" colspan="4" />
'''
    step_payment.code_before.new()
    step_payment.code_before[0].content = 'method'
    step_payment.code_before[0].technical_kind = 'step_before'
    step_payment.code_before[0].method_name = 'pre_calculate_fees'
    step_payment.code_after.new()
    step_payment.code_after[0].content = 'method'
    step_payment.code_after[0].technical_kind = 'step_after'
    step_payment.code_after[0].method_name = 'check_billing_information'
    step_payment.custom_views.new()
    step_payment.custom_views[0].view_name = 'billing_information'
    step_payment.custom_views[0].view_model, = IrModel.find(
        [('model', '=', 'contract.billing_information')])
    step_payment.custom_views[0].view_string = 'Quittancement'
    step_payment.custom_views[0].view_content = '''
<label name="billing_mode"/>
<field name="billing_mode" widget="selection" xexpand="0"/>
<newline/>
<label name="direct_debit_day_selector"/>
<field name="direct_debit_day_selector"/>
<label name="direct_debit_account"/>
<field name="direct_debit_account"/>
<label name="sepa_mandate"/>
<field name="sepa_mandate"/>
'''
    step_payment.save()
    # }}}

    do_print('    Creating step recapitulatif')  # {{{
    step_complete = ProcessStep()
    step_complete.fancy_name = 'Récapitulatif'
    step_complete.technical_name = 'recapitulatif'
    step_complete.button_domain = "[]"
    step_complete.main_model, = IrModel.find([('model', '=', 'contract')])
    step_complete.step_xml = '''
<notebook colspan="7">
    <page string="Covered Elements" id="cov_elements">
        <group id="covered_elements" yfill="1" yexpand="1">
            <hpaned id="covered_element" position="200">
                <child id="tree">
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        view_ids="contract_insurance.covered_elements_clean_tree"
                        mode="tree" expand_toolbar="0"/>
                </child>
                <child id="form">
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="form" relation="contract.covered_element"
                        view_ids="contract_insurance.covered_element_simple_view_form"
                        relation_field="contract" expand_toolbar="0"/>
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="form" relation="contract.option"
                        relation_field="covered_element"
                        view_ids="contract.option_view_form"
                        expand_toolbar="0"/>
                </child>
            </hpaned>
            <field name="options" colspan="4"/>
        </group>
    </page>
    <page string="Invoicing" id="invoicing">
        <field name="billing_informations" mode="form,tree" colspan="6"/>
        <field name="all_premiums" mode="tree,form" colspan="6"/>
    </page>
    <page string="Données complémentaires" id="extra_data">
        <field name="extra_data_values" no_command="1" colspan="4"/>
    </page>
</notebook>
'''
    step_complete.code_after.new()
    step_complete.code_after[0].content = 'method'
    step_complete.code_after[0].technical_kind = 'step_after'
    step_complete.code_after[0].method_name = 'activate_contract'
    step_complete.save()
    # }}}

    do_print('    Creating step recapitulatif emprunteur')  # {{{
    step_complete_loan = ProcessStep()
    step_complete_loan.fancy_name = 'Récapitulatif'
    step_complete_loan.technical_name = 'recapitulatif_emprunteur'
    step_complete_loan.button_domain = "[]"
    step_complete_loan.main_model, = IrModel.find(
        [('model', '=', 'contract')])
    step_complete_loan.step_xml = '''
<notebook colspan="6">
    <page string="Covered Elements" id="cov_elements">
        <group id="covered_elements" yfill="1" yexpand="1">
            <hpaned id="covered_element" position="200">
                <child id="tree">
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="tree"
                        view_ids="contract_insurance.covered_elements_clean_tree"
                        expand_toolbar="0"/>
                </child>
                <child id="form">
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="form" relation="contract.covered_element"
                        relation_field="contract"
                        view_ids="contract_insurance.covered_element_simple_view_form"
                        expand_toolbar="0"/>
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="form" relation="contract.option"
                        relation_field="covered_element"
                        view_ids="contract.option_view_form"
                        expand_toolbar="0"/>
                    <field name="multi_mixed_view" group="multi_mixed_view"
                        mode="form" relation="loan.share"
                        relation_field="option"
                        view_ids="loan.loan_share_view_form"
                        expand_toolbar="0"/>
                </child>
            </hpaned>
        </group>
    </page>
    <page string="Invoicing" id="invoicing">
        <field name="billing_informations" mode="form,tree" colspan="6"/>
    </page>
    <page string="Données complémentaires" id="extra_data">
        <field name="extra_data_values" no_command="1" colspan="4"/>
    </page>
</notebook>
<button name="button_show_all_invoices" string="Afficher l'échéancier"
    icon="bank" colspan="6"/>
'''
    step_complete_loan.code_before.new()
    step_complete_loan.code_before[0].content = 'method'
    step_complete_loan.code_before[0].technical_kind = 'step_before'
    step_complete_loan.code_before[0].method_name = \
        'force_calculate_prices'
    step_complete_loan.code_after.new()
    step_complete_loan.code_after[0].content = 'method'
    step_complete_loan.code_after[0].technical_kind = 'step_after'
    step_complete_loan.code_after[0].method_name = 'init_sepa_mandate'
    step_complete_loan.code_after.new()
    step_complete_loan.code_after[1].content = 'method'
    step_complete_loan.code_after[1].technical_kind = 'step_after'
    step_complete_loan.code_after[1].method_name = 'activate_contract'
    step_complete_loan.code_after.new()
    step_complete_loan.code_after[2].content = 'method'
    step_complete_loan.code_after[2].technical_kind = 'step_after'
    step_complete_loan.code_after[2].method_name = '_first_invoice'
    step_complete_loan.code_after[2].parameters = 'True'
    step_complete_loan.save()
    # }}}

    do_print('    Creating claim info step')  # {{{
    step_claim_info = ProcessStep()
    step_claim_info.fancy_name = 'Informations générales'
    step_claim_info.technical_name = 'step_claim_info'
    step_claim_info.button_domain = "[]"
    step_claim_info.main_model, = IrModel.find([('model', '=', 'claim')])
    step_claim_info.step_xml = '''
<field name="losses" colspan="4" mode="form,tree"
    view_ids="claim.loss_without_service_view_form"/>
'''
    step_claim_info.code_after.new()
    step_claim_info.code_after[-1].content = 'rule'
    step_claim_info.code_after[-1].technical_kind = 'step_after'
    step_claim_info.code_after[-1].target_path = 'object.losses'
    step_claim_info.code_after[-1].rule = claim_info_step_validation
    step_claim_info.code_after.new()
    step_claim_info.code_after[-1].content = 'method'
    step_claim_info.code_after[-1].technical_kind = 'step_after'
    step_claim_info.code_after[-1].method_name = 'activate_losses'
    step_claim_info.code_after.new()
    step_claim_info.code_after[-1].content = 'method'
    step_claim_info.code_after[-1].technical_kind = 'step_after'
    step_claim_info.code_after[-1].method_name = 'deliver_automatic_benefit'
    step_claim_info.save()
    # }}}

    do_print('    Creating claim benefit control step')  # {{{
    step_benefit_check = ProcessStep()
    step_benefit_check.fancy_name = 'Validation des droits'
    step_benefit_check.technical_name = 'step_benefit_check'
    step_benefit_check.button_domain = "[]"
    step_benefit_check.main_model, = IrModel.find([('model', '=', 'claim')])
    step_benefit_check.step_xml = '''
<group id="eligibility" colspan="4"
    states="{&quot;invisible&quot;:{&quot;__class__&quot;: ''' + \
        '&quot;Not&quot;, &quot;v&quot;: {&quot;__class__&quot;: ' + \
        '&quot;Bool&quot;, &quot;v&quot;: {&quot;d&quot;: &quot;&quot;, ' + \
        '&quot;__class__&quot;: &quot;Eval&quot;, &quot;v&quot;: ' + \
        '''&quot;delivered_services&quot;}} }}" yfill="1" yexpand="1">
    <hpaned id="service_decision" position="200">
        <child id="tree">
            <field name="delivered_services" group="services"
                view_ids="claim_eligibility.claim_service_simple_view_list"
                expand_toolbar="0"/>
        </child>
        <child id="form">
            <field name="delivered_services" group="services"
                view_ids="claim_eligibility.claim_service_simple_view_form"
                expand_toolbar="0"/>
        </child>
    </hpaned>
    <field name="is_services_deductible"  invisible="1"/>
</group>
<group id="user_message" colspan="4"
    states="{&quot;invisible&quot;:{&quot;__class__&quot;: ''' + \
        '&quot;Not&quot;, &quot;v&quot;: {&quot;__class__&quot;:' + \
        '&quot;Not&quot;, &quot;v&quot;: {&quot;__class__&quot;:' + \
        '&quot;Bool&quot;, &quot;v&quot;: {&quot;d&quot;: &quot;&quot;,' + \
        '&quot;__class__&quot;: &quot;Eval&quot;, &quot;v&quot;:' + \
        '''&quot;delivered_services&quot;}} } }}">
    <image name="tryton-dialog-warning" xexpand="0" xfill="0" />
    <label id="user_warning_message"
        string="Attention ! Aucune prestation ne peut être délivrée." />
</group>
<newline />
<group id="document" colspan="4" yfill="1" yexpand="1">
    <field name="document_request_lines" colspan="4"/>
    <field name="doc_received" invisible="1"/>
</group>
<field name="beneficiaries" colspan="4"/>
'''
    step_benefit_check.code_before.new()
    step_benefit_check.code_before[-1].content = 'method'
    step_benefit_check.code_before[-1].technical_kind = 'step_before'
    step_benefit_check.code_before[-1].method_name = 'check_eligibility'
    step_benefit_check.code_before.new()
    step_benefit_check.code_before[-1].content = 'method'
    step_benefit_check.code_before[-1].technical_kind = 'step_before'
    step_benefit_check.code_before[-1].method_name = \
        'init_declaration_document_request'
    step_benefit_check.code_before.new()
    step_benefit_check.code_before[-1].content = 'method'
    step_benefit_check.code_before[-1].technical_kind = 'step_before'
    step_benefit_check.code_before[-1].method_name = \
        'link_attachments_to_requests'
    step_benefit_check.save()
    # }}}

    do_print('    Creating claim salary step')  # {{{
    step_claim_salary = ProcessStep()
    step_claim_salary.fancy_name = 'Salaires'
    step_claim_salary.technical_name = 'step_claim_salary'
    step_claim_salary.button_domain = "[]"
    step_claim_salary.pyson = "Eval('all_services_refused')"
    step_claim_salary.main_model, = IrModel.find([('model', '=', 'claim')])
    step_claim_salary.step_xml = '''
<label name="losses_description"/>
<field name="losses_description" colspan="3"/>
<button string="Saisie des salaires" name="launch_salaries_wizard"/>
<field name="delivered_services"  colspan="4" mode="form,tree"
    view_ids="claim_salary_fr.claim_service_with_salary_view_form"
    expand_toolbar="0"/>
<field name="delivered_services" invisible="1"/>
'''
    step_claim_salary.save()
    # }}}

    do_print('    Creating claim services step')  # {{{
    step_claim_services = ProcessStep()
    step_claim_services.fancy_name = 'Prestations'
    step_claim_services.technical_name = 'step_claim_services'
    step_claim_services.button_domain = "[]"
    step_claim_services.pyson = "Eval('all_services_refused')"
    step_claim_services.main_model, = IrModel.find([('model', '=', 'claim')])
    step_claim_services.step_xml = '''
<button string="Nouvelle période/capital" name="create_indemnification"
    colspan="4" icon="plus"/>
<field name="indemnifications_details" colspan="4"/>
<field name="doc_received" invisible="1"/>
<field name="delivered_services" invisible="1"/>
'''
    step_claim_services.save()
    # }}}

    do_print('    Creating claim indemnification validation step')  # {{{
    step_indemnification_validation = ProcessStep()
    step_indemnification_validation.fancy_name = 'Ordonnancement'
    step_indemnification_validation.technical_name = \
        'step_indemnification_validation'
    step_indemnification_validation.button_domain = "[]"
    step_indemnification_validation.main_model, = IrModel.find(
        [('model', '=', 'claim')])
    step_indemnification_validation.step_xml = '''
<field name="indemnifications" invisible="1"/>
<field name="has_calculated_indemnification" invisible="1"/>
<field name="delivered_services" invisible="1"/>
<newline/>
<label name="losses_description"/>
<field name="losses_description" colspan="3"/>
    <notebook>
        <page string="Losses" id="losses">
            <field name="indemnifications_to_schedule" colspan="4"/>
        </page>
        <page string="Documents" id="documents">
            <field name="attachments" colspan="4"/>
        </page>
    </notebook>
<field name="is_pending_indemnification"/>
<field name="all_services_refused" invisible="1"/>
'''
    step_indemnification_validation.code_after.new()
    step_indemnification_validation.code_after[-1].content = 'method'
    step_indemnification_validation.code_after[-1].technical_kind = 'step_after'
    step_indemnification_validation.code_after[-1].method_name = \
        'validate_indemnifications'
    step_indemnification_validation.save()
    # }}}

    do_print('    Creating claim closing step')  # {{{
    step_claim_close = ProcessStep()
    step_claim_close.fancy_name = 'Clôture du dossier'
    step_claim_close.technical_name = \
        'step_claim_close'
    step_claim_close.button_domain = "[]"
    step_claim_close.main_model, = IrModel.find(
        [('model', '=', 'claim')])
    step_claim_close.step_xml = '''
<label name="name"/>
<field name="name"/>
<label name="sub_status"/>
<field name="sub_status"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<label name="claimant"/>
<field name="claimant"/>
<field name="all_services_refused" invisible="1"/>
<field name="doc_received" invisible="1"/>
<field name="is_pending_indemnification" invisible="1"/>
'''
    step_claim_close.entering_wizard, = IrAction.find(
        [('xml_id', '=', 'claim_process.act_close_claim_wizard')])
    step_claim_close.save()
    # }}}

    # TODO : Add underwriting steps for subscription
    do_print('\nCreating processes')
    do_print('    Creating process souscription_generique')  # {{{
    generic_process = Process()
    generic_process.technical_name = 'souscription_generique'
    generic_process.fancy_name = 'Souscription Générique'
    generic_process.on_model, = IrModel.find([('model', '=', 'contract')])
    generic_process.kind = 'subscription'
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_subscriber
    generic_process.all_steps[-1].order = 0
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_covered
    generic_process.all_steps[-1].order = 1
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_options
    generic_process.all_steps[-1].order = 2
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_documents
    generic_process.all_steps[-1].order = 3
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_payment
    generic_process.all_steps[-1].order = 4
    generic_process.all_steps.new()
    generic_process.all_steps[-1].step = step_complete
    generic_process.all_steps[-1].order = 5
    generic_process.menu_icon = 'tryton-open'
    generic_process.close_tab_on_completion = True
    generic_process.complete_message = 'Le contrat sera actif après ' + \
        'cette étape, êtes-vous sûr de vouloir continuer ?'
    generic_process.delete_button = 'Supprimer le devis'
    generic_process.end_step_name = 'Activer le contrat'
    generic_process.hold_button = 'Mettre en attente'
    generic_process.menu_name = 'Souscription générique'
    generic_process.step_button_group_position = 'right'
    generic_process.steps_implicitly_available = True
    generic_process.with_prev_next = True
    generic_process.xml_tree = '''
<field name="current_state"/>
<field name="contract_number"/>
<field name="subscriber"/>
<field name="status"/>
<field name="start_date"/>
<field name="product"/>
'''
    generic_process.xml_header = '''
<label name="product"/>
<field name="product" readonly="1"/>
<label name="rec_name"/>
<field name="rec_name"/>
<label name="start_date"/>
<field name="start_date" readonly="1"/>
<label name="subscriber"/>
<group id="subscriber" col="99">
    <field name="subscriber_kind"/>
    <group id="person" states="{&quot;invisible&quot;: ''' + \
'{&quot;__class__&quot;: &quot;Not&quot;, &quot;v&quot;: {&quot;s2&quot;: ' + \
'&quot;person&quot;, &quot;s1&quot;: {&quot;d&quot;: &quot;&quot;, ' + \
'&quot;__class__&quot;: &quot;Eval&quot;, &quot;v&quot;: ' + \
'&quot;subscriber_kind&quot;}, &quot;__class__&quot;: &quot;Equal&quot;} ' + \
'''}}" colspan="40">
        <field name="subscriber" view_ids="party_cog.person_view_tree"/>
    </group>
    <group id="company" states="{&quot;invisible&quot;: {&quot;s2&quot;:''' + \
'&quot;person&quot;, &quot;s1&quot;: {&quot;d&quot;: &quot;&quot;,' + \
'&quot;__class__&quot;: &quot;Eval&quot;, &quot;v&quot;:' + \
'&quot;subscriber_kind&quot;}, &quot;__class__&quot;: &quot;Equal&quot;}}"' + \
''' colspan="40">
        <field name="subscriber"/>
    </group>
</group>
'''
    generic_process.save()
    # }}}

    do_print('    Creating process souscription_prevoyance')  # {{{
    life_process = Process()
    life_process.technical_name = 'souscription_prevoyance'
    life_process.fancy_name = 'Souscription Prévoyance'
    life_process.on_model, = IrModel.find([('model', '=', 'contract')])
    life_process.kind = 'subscription'
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_life_subscriber
    life_process.all_steps[-1].order = 0
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_covered
    life_process.all_steps[-1].order = 1
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_options
    life_process.all_steps[-1].order = 2
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_documents
    life_process.all_steps[-1].order = 3
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_underwriting
    life_process.all_steps[-1].order = 4
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_payment
    life_process.all_steps[-1].order = 5
    life_process.all_steps.new()
    life_process.all_steps[-1].step = step_complete
    life_process.all_steps[-1].order = 6
    life_process.menu_icon = 'tryton-open'
    life_process.close_tab_on_completion = True
    life_process.complete_message = 'Le contrat sera actif après ' + \
        'cette étape, êtes-vous sûr de vouloir continuer ?'
    life_process.delete_button = 'Supprimer le devis'
    life_process.end_step_name = 'Activer le contrat'
    life_process.hold_button = 'Mettre en attente'
    life_process.menu_name = 'Souscription Prévoyance'
    life_process.step_button_group_position = 'right'
    life_process.steps_implicitly_available = True
    life_process.with_prev_next = True
    life_process.xml_tree = generic_process.xml_tree
    life_process.xml_header = generic_process.xml_header
    life_process.save()
    # }}}

    do_print('    Creating process souscription_emprunteur')  # {{{
    loan_process = Process()
    loan_process.technical_name = 'souscription_emprunteur'
    loan_process.fancy_name = 'Souscription Emprunteur'
    loan_process.on_model, = IrModel.find([('model', '=', 'contract')])
    loan_process.kind = 'subscription'
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_life_subscriber
    loan_process.all_steps[-1].order = 0
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_covered_loan
    loan_process.all_steps[-1].order = 1
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_options_loan
    loan_process.all_steps[-1].order = 2
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_documents
    loan_process.all_steps[-1].order = 3
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_payment
    loan_process.all_steps[-1].order = 4
    loan_process.all_steps.new()
    loan_process.all_steps[-1].step = step_complete_loan
    loan_process.all_steps[-1].order = 5
    loan_process.menu_icon = 'tryton-open'
    loan_process.close_tab_on_completion = True
    loan_process.complete_message = 'Le contrat sera actif après ' + \
        'cette étape, êtes-vous sûr de vouloir continuer ?'
    loan_process.delete_button = 'Supprimer le devis'
    loan_process.end_step_name = 'Activer le contrat'
    loan_process.hold_button = 'Mettre en attente'
    loan_process.menu_name = 'Souscription Prévoyance'
    loan_process.step_button_group_position = 'right'
    loan_process.steps_implicitly_available = True
    loan_process.with_prev_next = True
    loan_process.xml_tree = generic_process.xml_tree
    loan_process.xml_header = generic_process.xml_header
    loan_process.save()
    # }}}

    do_print('    Creating death claim process')  # {{{
    claim_death_process = Process()
    claim_death_process.technical_name = 'claim_death_process'
    claim_death_process.fancy_name = "Déclaration de décès"
    claim_death_process.on_model, = IrModel.find([('model', '=', 'claim')])
    claim_death_process.kind = 'claim_declaration'
    claim_death_process.all_steps.new()
    claim_death_process.all_steps[-1].step = step_claim_info
    claim_death_process.all_steps[-1].order = 1
    claim_death_process.all_steps.new()
    claim_death_process.all_steps[-1].step = step_benefit_check
    claim_death_process.all_steps[-1].order = 2
    claim_death_process.all_steps.new()
    claim_death_process.all_steps[-1].step = step_claim_services
    claim_death_process.all_steps[-1].order = 3
    claim_death_process.all_steps.new()
    claim_death_process.all_steps[-1].step = step_indemnification_validation
    claim_death_process.all_steps[-1].order = 4
    claim_death_process.all_steps.new()
    claim_death_process.all_steps[-1].step = step_claim_close
    claim_death_process.all_steps[-1].order = 5
    claim_death_process.menu_icon = 'tryton-open'
    claim_death_process.end_step_name = 'Terminer'
    claim_death_process.hold_button = 'Suspendre'
    claim_death_process.menu_name = "Déclaration de décès"
    claim_death_process.step_button_group_position = 'right'
    claim_death_process.steps_implicitly_available = False
    claim_death_process.custom_transitions = True
    claim_death_process.xml_tree = '''
<field name="current_state"/>
<field name="name"/>
<field name="claimant"/>
<field name="status"/>
'''
    claim_death_process.xml_header = '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant" readonly="1"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
'''
    transitions = [  # {{{
        ('start', None, step_claim_info,
            [('add_new_loss', "'death'")], ''),
        ('standard', step_claim_info, step_benefit_check,
            [('activate_underwritings_if_needed', '')], ''),
        ('standard', step_benefit_check, step_claim_info, [], ''),
        ('standard', step_benefit_check, step_claim_services, [], ''),
        ('standard', step_benefit_check, step_indemnification_validation, [],
            ''),
        ('standard', step_benefit_check, step_claim_close, [], ''),
        ('standard', step_claim_services, step_benefit_check, [], ''),
        ('standard', step_claim_services, step_claim_info, [], ''),
        ('standard', step_claim_services, step_indemnification_validation, [],
            ''),
        ('standard', step_claim_services, step_claim_close, [], ''),
        ('standard', step_indemnification_validation, step_claim_services, [],
            ''),
        ('standard', step_indemnification_validation, step_benefit_check, [],
            ''),
        ('standard', step_indemnification_validation, step_claim_info, [], ''),
        ('standard', step_indemnification_validation, step_claim_close, [],
            ''),
        ('standard', step_claim_close, step_indemnification_validation, [],
            ''),
        ('complete', step_claim_close, None, [], ''),
        ]
    for data in transitions:
        claim_death_process.transitions.new()
        transition = claim_death_process.transitions[-1]
        if data[0] == 'complete':
            transition.name = 'Terminer'
        transition.kind = data[0]
        transition.method_kind = 'add'
        transition.from_step = data[1]
        transition.to_step = data[2]
        for name, params in data[3]:
            transition.methods.new()
            transition.methods[-1].content = 'method'
            transition.methods[-1].technical_kind = 'transition'
            transition.methods[-1].method_name = name
            transition.methods[-1].parameters = params or ''
        if data[4]:
            transition.pyson = data[4]
        # }}}
    claim_death_process.save()
    # }}}

    do_print('    Creating claim work interruption process')  # {{{
    claim_work_interruption_process = Process()
    claim_work_interruption_process.technical_name = \
        'claim_work_interruption_process'
    claim_work_interruption_process.fancy_name = \
        "Déclaration d'arrêt de travail"
    claim_work_interruption_process.on_model, = \
        IrModel.find([('model', '=', 'claim')])
    claim_work_interruption_process.kind = 'claim_declaration_and_reopening'
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = step_claim_info
    claim_work_interruption_process.all_steps[-1].order = 1
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = step_benefit_check
    claim_work_interruption_process.all_steps[-1].order = 2
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = step_claim_salary
    claim_work_interruption_process.all_steps[-1].order = 3
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = step_claim_services
    claim_work_interruption_process.all_steps[-1].order = 4
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = \
        step_indemnification_validation
    claim_work_interruption_process.all_steps[-1].order = 5
    claim_work_interruption_process.all_steps.new()
    claim_work_interruption_process.all_steps[-1].step = step_claim_close
    claim_work_interruption_process.all_steps[-1].order = 6
    claim_work_interruption_process.menu_icon = 'tryton-open'
    claim_work_interruption_process.end_step_name = 'Terminer'
    claim_work_interruption_process.hold_button = 'Suspendre'
    claim_work_interruption_process.menu_name = \
        "Déclaration d'arrêt de travail"
    claim_work_interruption_process.step_button_group_position = 'right'
    claim_work_interruption_process.steps_implicitly_available = False
    claim_work_interruption_process.custom_transitions = True
    claim_work_interruption_process.xml_tree = '''
<field name="current_state"/>
<field name="name"/>
<field name="claimant"/>
<field name="status"/>
'''
    claim_work_interruption_process.xml_header = '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant" readonly="1"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
'''
    transitions = [  # {{{
        ('start', None, step_claim_info,
            [('add_new_loss', "'temporary_work_interruption', True")], ''),
        ('standard', step_claim_info, step_benefit_check,
            [('activate_underwritings_if_needed', '')], ''),
        ('standard', step_benefit_check, step_claim_info, [], ''),
        ('standard', step_benefit_check, step_claim_salary, [], ''),
        ('standard', step_benefit_check, step_claim_services, [], ''),
        ('standard', step_benefit_check, step_indemnification_validation, [],
            ''),
        ('standard', step_benefit_check, step_claim_close, [], ''),
        ('standard', step_claim_salary, step_claim_info, [], ''),
        ('standard', step_claim_salary, step_claim_services, [],
            "~Bool(Eval('delivered_services'))"),
        ('standard', step_claim_salary, step_benefit_check, [], ''),
        ('standard', step_claim_salary, step_indemnification_validation, [],
            ''),
        ('standard', step_claim_salary, step_claim_close, [], ''),
        ('standard', step_claim_services, step_claim_salary, [], ''),
        ('standard', step_claim_services, step_benefit_check, [], ''),
        ('standard', step_claim_services, step_claim_info, [], ''),
        ('standard', step_claim_services, step_indemnification_validation, [],
            ''),
        ('standard', step_claim_services, step_claim_close, [], ''),
        ('standard', step_indemnification_validation, step_claim_services, [],
            ''),
        ('standard', step_indemnification_validation, step_claim_salary, [],
            ''),
        ('standard', step_indemnification_validation, step_benefit_check, [],
            ''),
        ('standard', step_indemnification_validation, step_claim_info, [], ''),
        ('standard', step_indemnification_validation, step_claim_close, [],
            ''),
        ('standard', step_claim_close, step_indemnification_validation, [],
            ''),
        ('complete', step_claim_close, None, [], ''),
        ]
    for data in transitions:
        claim_work_interruption_process.transitions.new()
        transition = claim_work_interruption_process.transitions[-1]
        if data[0] == 'complete':
            transition.name = 'Terminer'
        transition.kind = data[0]
        transition.method_kind = 'add'
        transition.from_step = data[1]
        transition.to_step = data[2]
        for name, params in data[3]:
            transition.methods.new()
            transition.methods[-1].content = 'method'
            transition.methods[-1].technical_kind = 'transition'
            transition.methods[-1].method_name = name
            transition.methods[-1].parameters = params or ''
        if data[4]:
            transition.pyson = data[4]
        # }}}
    claim_work_interruption_process.save()
    # }}}
# }}}

if CREATE_ACTORS:  # {{{
    do_print('\nCreating Actors')
    do_print('    Creating insurers')  # {{{
    insurer_party = Party(
        name=_insurer_name,
        lang=lang,
        )
    insurer_party.all_addresses[0].street = "\n\n2 rue d'Hauteville"
    insurer_party.all_addresses[0].zip = '75004'
    insurer_party.all_addresses[0].city = 'PARIS'
    insurer_party.all_addresses[0].country = country
    insurer_party.save()
    insurer = Insurer()
    insurer.party = insurer_party
    insurer.save()
    # }}}

    do_print('    Creating brokers')  # {{{
    broker_party = Party(
        name=_broker_name,
        lang=lang,
        )
    broker_party.all_addresses[0].street = "\n\n2 rue d'Hauteville"
    broker_party.all_addresses[0].zip = '75004'
    broker_party.all_addresses[0].city = 'PARIS'
    broker_party.all_addresses[0].country = country
    broker_party.save()
    # }}}

    do_print('    Creating distribution network')  # {{{
    run_test_cases(['distribution_network_test_case'])
    brokers = DistributionNetwork.find([('code', '=', 'C1')])
    for broker in brokers:
        broker.party = broker_party
        broker.is_broker = True
        broker.save()

    for distributor in DistributionNetwork.find([('code', 'like', 'C101010%')]):
        distributor.is_distributor = True
        distributor.authorized_distribution_channels.append(Channel.find([])[0])
        distributor.save()
    # }}}

    do_print('    Creating lender')  # {{{
    lender_party = Party(
        name=_lender_name,
        lang=lang,
        )
    lender_party.all_addresses[0].street = "\n\n2 rue d'Hauteville"
    lender_party.all_addresses[0].zip = '75004'
    lender_party.all_addresses[0].city = 'PARIS'
    lender_party.all_addresses[0].country = country
    lender_party.lender_role.new()
    lender_party.save()
    # }}}

    do_print('    Creating french state')  # {{{
    french_state = Party()
    french_state.name = 'État français'
    french_state.save()
    # }}}
# }}}

if CREATE_PRODUCTS:  # {{{
    do_print('\nLoading required configuration')  # {{{
    insurer, = Insurer.find([])
    generic_process, = Process.find(
        [('technical_name', '=', 'souscription_generique')])
    life_process, = Process.find(
        [('technical_name', '=', 'souscription_prevoyance')])
    loan_process, = Process.find(
        [('technical_name', '=', 'souscription_emprunteur')])
    death_claim_process, = Process.find(
        [('technical_name', '=', 'claim_death_process')])
    work_interruption_claim_process, = Process.find(
        [('technical_name', '=', 'claim_work_interruption_process')])
    claim_product, = AccountProduct.find([('code', '=', 'reglement_sinistres')])
    claim_product_taxed, = AccountProduct.find(
        [('code', '=', 'reglement_sinistres_taxes')])
    claim_product_taxed, = AccountProduct.find(
        [('code', '=', 'reglement_sinistres_taxes')])
    claim_product_reduced_taxed, = AccountProduct.find(
        [('code', '=', 'reglement_sinistres_taxes_reduites')])
    # }}}

    do_print('\nCreating claim sub status')  # {{{
    non_eligible = ClaimSubStatus()
    non_eligible.code = 'non_eligible'
    non_eligible.name = 'Non éligible'
    non_eligible.status = 'closed'
    non_eligible.save()

    paid = ClaimSubStatus()
    paid.code = 'paid'
    paid.name = 'Payé'
    paid.status = 'closed'
    paid.save()
    # }}}

    do_print('\nCreating option detail definition')  # {{{
    option_extra_details_conf = ExtraDetails()
    option_extra_details_conf.model_name = 'contract.option.version'
    option_extra_details_conf.lines.new()
    option_extra_details_conf.lines[0].string = 'Valeur de rachat'
    option_extra_details_conf.lines[0].name = 'valeur_rachat'
    option_extra_details_conf.lines[0].type_ = 'numeric'
    option_extra_details_conf.lines.new()
    option_extra_details_conf.lines[1].string = 'Valeur de réduction'
    option_extra_details_conf.lines[1].name = 'valeur_reduction'
    option_extra_details_conf.lines[1].type_ = 'numeric'
    option_extra_details_conf.save()
    # }}}

    do_print('\nCreating document types')  # {{{
    subscription_request = DocumentDescription()
    subscription_request.code = 'subscription_request'
    subscription_request.name = "Demande d\'adhésion"
    subscription_request.save()
    loan_planning = DocumentDescription()
    loan_planning.code = 'loan_planning'
    loan_planning.name = "Échéancier des prêts"
    loan_planning.save()
    # }}}

    do_print('\nCreating clauses')  # {{{
    standard_beneficiary_clause = Clause()
    standard_beneficiary_clause.name = 'Clause bénéficiaire standard'
    standard_beneficiary_clause.code = 'clause_beneficiaire_standard'
    standard_beneficiary_clause.kind = 'beneficiary'
    standard_beneficiary_clause.customizable = False
    standard_beneficiary_clause.content = 'Mon conjoint, à défaut mes ' + \
        'enfants, nés et à naître, vivants ou représentés, par parts ' + \
        'égales; à défaut mes héritiers'
    standard_beneficiary_clause.save()

    custom_beneficiary_clause = Clause()
    custom_beneficiary_clause.name = 'Clause bénéficiaire personnalisée'
    custom_beneficiary_clause.code = 'clause_beneficiaire_personnalisee'
    custom_beneficiary_clause.kind = 'beneficiary'
    custom_beneficiary_clause.customizable = True
    custom_beneficiary_clause.content = ''
    custom_beneficiary_clause.save()

    loan_beneficiary_clause = Clause()
    loan_beneficiary_clause.name = 'Clause bénéficiaire emprunteur'
    loan_beneficiary_clause.code = 'clause_beneficiaire_emprunteur'
    loan_beneficiary_clause.kind = 'beneficiary'
    loan_beneficiary_clause.customizable = False
    loan_beneficiary_clause.content = 'A concurrence du capital restant ' + \
        'dû. L\'assureur ou son représentant s\'engage à informer le ' + \
        'bénéficiaire acceptant, qu\'aucune modification au contrat, y ' + \
        'compris la résiliation, ne puisse avoir lieu sans son ' + \
        'consentement et que tout impayé de primes sera porté à sa ' + \
        'connaissance.'
    loan_beneficiary_clause.save()

    funeral_beneficiary_clause = Clause()
    funeral_beneficiary_clause.name = 'Clause bénéficiaire obsèques'
    funeral_beneficiary_clause.code = 'clause_beneficiaire_obseques'
    funeral_beneficiary_clause.kind = 'beneficiary'
    funeral_beneficiary_clause.customizable = False
    funeral_beneficiary_clause.content = "La personne physique ou " + \
        "l'entreprise de pompes funèbres ayant financé ou pris en charge " + \
        "mes obsèques, à hauteur des frais engagés, le solde revenant à " + \
        "mon conjoint, à défaut par parts égales à mes enfants nés ou à " + \
        "naître, à défaut par parts égales à mes héritiers."
    funeral_beneficiary_clause.save()
    # }}}

    do_print('\nCreating product accounts')  # {{{
    coverage_root = Account.find([('code', '=', '4011')])[0]

    def create_coverage_account(name, code):
        account = Account()
        account.company = company
        account.name = name
        account.code = code
        account.template = coverage_root.template
        account.type = coverage_root.type
        account.parent = coverage_root
        account.party_required = True
        account.save()
        return account

    fire_coverage_account = create_coverage_account(
        'Compte de garantie incendie', '40110001')
    responsability_coverage_account = create_coverage_account(
        'Compte de garantie responsabilité civile', '40110002')
    death_coverage_account = create_coverage_account(
        'Compte de garantie décès', '40110011')
    unemployment_coverage_account = create_coverage_account(
        'Compte de garantie incapacité', '40110012')
    disability_coverage_account = create_coverage_account(
        'Compte de garantie invalidité', '40110013')
    death_loan_coverage_account = create_coverage_account(
        'Compte de garantie décès', '40110021')
    unemployment_loan_coverage_account = create_coverage_account(
        'Compte de garantie incapacité', '40110022')
    disability_loan_coverage_account = create_coverage_account(
        'Compte de garantie invalidité', '40110023')
    funeral_coverage_account = create_coverage_account(
        'Compte de garantie obsèques', '40110031')
    funeral_surrender_account = create_coverage_account(
        'Compte de rachat obsèques', '40111031')
    group_death_coverage_account = create_coverage_account(
        'Compte de rachat décès collectif', '40110041')
    group_incapacity_coverage_account = create_coverage_account(
        'Compte de rachat incapacité collectif', '40110042')
    group_invalidity_coverage_account = create_coverage_account(
        'Compte de rachat invalidité collectif', '40110043')
    # }}}

    do_print('\nCreating Sequences')  # {{{
    contract_sequence = Sequence()
    contract_sequence.name = 'Numéros de contrats'
    contract_sequence.code = 'contract'
    contract_sequence.company = company
    contract_sequence.save()

    quote_sequence = Sequence()
    quote_sequence.name = 'Numéros de devis'
    quote_sequence.code = 'quote'
    quote_sequence.company = company
    quote_sequence.save()

    prest_ij_sequence = Sequence()
    prest_ij_sequence.name = 'Numéros PrestIJ'
    prest_ij_sequence.code = 'claim'
    prest_ij_sequence.company = company
    prest_ij_sequence.save()

    prest_ij_period_sequence = Sequence()
    prest_ij_period_sequence.name = 'Numéros de période PrestIJ'
    prest_ij_period_sequence.code = 'claim'
    prest_ij_period_sequence.company = company
    prest_ij_period_sequence.save()

    try:
        loan_sequence, = Sequence.find([('code', '=', 'loan')])
    except ValueError:
        # When testing, the sequence will not be created when installing the
        # module
        loan_sequence = Sequence()
        loan_sequence.name = 'Numéro de prêts'
        loan_sequence.code = 'loan'
        loan_sequence.company = company
        loan_sequence.save()
    # }}}

    do_print('\nSlip Configuration')  # {{{
    slip_configuration = InvoiceSlipConfiguration()
    slip_configuration.party = french_state
    slip_configuration.name = 'Bordereau de taxes'
    slip_configuration.accounts.append(Account(csg_tax_account.id))
    slip_configuration.accounts.append(Account(csg_deductible_tax_account.id))
    slip_configuration.accounts.append(Account(crds_tax_account.id))
    slip_configuration.accounts.append(Account(pasrau_tax_account.id))
    slip_configuration.slip_kind = 'pasrau'
    exp_journal, = Journal.find([('code', '=', 'EXP')])
    slip_configuration.journal = exp_journal
    slip_configuration.save()
    # }}}

    do_print('\nCreating Extra Data')
    do_print('    Product')  # {{{
    libelle_editique = ExtraData()
    libelle_editique.type_ = 'char'
    libelle_editique.kind = 'product'
    libelle_editique.string = 'Libellé éditique'
    libelle_editique.name = 'libelle_editique'
    libelle_editique.save()
    # }}}

    do_print('    Contract')  # {{{
    reduction_libre = ExtraData()
    reduction_libre.type_ = 'selection'
    reduction_libre.kind = 'contract'
    reduction_libre.string = 'Réduction libre'
    reduction_libre.name = 'reduction_libre'
    reduction_libre.selection = '''0: -
10: 10 %
20: 20%
30: 30%
'''
    reduction_libre.has_default_value = True
    reduction_libre.default_value = '0'
    reduction_libre.save()
    # }}}

    do_print('    Contract Underwriting')  # {{{
    analyse_forcee = ExtraData()
    analyse_forcee.type_ = 'selection'
    analyse_forcee.kind = 'contract_underwriting'
    analyse_forcee.string = 'Analyse forcée'
    analyse_forcee.name = 'analyse_forcee'
    analyse_forcee.selection = '''oui: Oui
non: None
'''
    analyse_forcee.has_default_value = True
    analyse_forcee.default_value = 'non'
    analyse_forcee.save()
    # }}}

    do_print('    Item Desc')  # {{{
    objet_du_pret = ExtraData()
    objet_du_pret.type_ = 'selection'
    objet_du_pret.kind = 'loan'
    objet_du_pret.string = 'Objet du prêt'
    objet_du_pret.name = 'objet_du_pret'
    objet_du_pret.selection = '''non_renseigne: -
residence_principale: Achat d'une résidence principale
terrain: Achat d'un terrain
construction: Financement de la construction de la résidence principale
scpi: Achat de parts de SCPI
autre: Autres
'''
    objet_du_pret.save()

    house_floor = ExtraData()
    house_floor.type_ = 'integer'
    house_floor.kind = 'covered_element'
    house_floor.string = 'Étage'
    house_floor.name = 'house_floor'
    house_floor.save()

    house_type = ExtraData()
    house_type.type_ = 'selection'
    house_type.kind = 'covered_element'
    house_type.string = "Type d'habitation"
    house_type.name = 'house_type'
    house_type.selection = '''appartement: Appartement
maison: Maison Individuelle
duplex: Duplex
sousplex: Sousplex
'''
    house_type.sub_datas.new()
    house_type.sub_datas[0].select_value = 'appartement'
    house_type.sub_datas[0].child = house_floor
    house_type.save()

    house_rooms = ExtraData()
    house_rooms.type_ = 'integer'
    house_rooms.kind = 'covered_element'
    house_rooms.string = 'Nombre de pièces'
    house_rooms.name = 'house_rooms'
    house_rooms.save()

    house_size = ExtraData()
    house_size.type_ = 'integer'
    house_size.kind = 'covered_element'
    house_size.string = 'Superficie (m²)'
    house_size.name = 'house_size'
    house_size.save()

    house_construction_date = ExtraData()
    house_construction_date.type_ = 'integer'
    house_construction_date.kind = 'covered_element'
    house_construction_date.string = 'Année de construction'
    house_construction_date.name = 'house_construction_date'
    house_construction_date.save()

    job_category = ExtraData()
    job_category.type_ = 'selection'
    job_category.kind = 'covered_element'
    job_category.string = 'Catégorie Socio-professionnelle'
    job_category.name = 'job_category'
    job_category.selection = '''csp1: CSP1
csp2: CSP2
csp3: CSP3
'''
    job_category.save()

    co_borrower_relation = ExtraData()
    co_borrower_relation.type_ = 'selection'
    co_borrower_relation.kind = 'covered_element'
    co_borrower_relation.string = 'Relation avec le co-emprunteur'
    co_borrower_relation.name = 'co_borrower_relation'
    co_borrower_relation.selection = '''aucune: Aucune
mariage: Marié(e)
pacs: Pacsé(e)
'''
    co_borrower_relation.save()

    employee_type = ExtraData()
    employee_type.type_ = 'selection'
    employee_type.kind = 'covered_element'
    employee_type.string = "Type d'employé"
    employee_type.name = 'employee_type'
    employee_type.selection = '''cadre: Cadre
non_cadre: Non cadre
dirigeant: Dirigeant
autre: Autre
'''
    employee_type.save()

    job_start = ExtraData()
    job_start.type_ = 'date'
    job_start.kind = 'covered_element'
    job_start.string = "Date d'entrée"
    job_start.name = 'job_start'
    job_start.save()

    job_end = ExtraData()
    job_end.type_ = 'date'
    job_end.kind = 'covered_element'
    job_end.string = 'Date de sortie'
    job_end.name = 'job_end'
    job_end.save()
    # }}}

    do_print('    Option')  # {{{
    fire_damage_limit = ExtraData()
    fire_damage_limit.type_ = 'selection'
    fire_damage_limit.kind = 'option'
    fire_damage_limit.string = "Plafond de remboursement"
    fire_damage_limit.name = 'fire_damage_limit'
    fire_damage_limit.selection = '''1000: 1000
2000: 2000
5000: 5000
10000: 10000
'''
    fire_damage_limit.save()

    electrical_fires = ExtraData()
    electrical_fires.type_ = 'boolean'
    electrical_fires.kind = 'option'
    electrical_fires.string = "Couverture des incendies d'origine électrique"
    electrical_fires.name = 'electrical_fires'
    electrical_fires.save()

    double_for_accidents = ExtraData()
    double_for_accidents.type_ = 'boolean'
    double_for_accidents.kind = 'option'
    double_for_accidents.string = "Doublement en cas d'accident"
    double_for_accidents.name = 'double_for_accidents'
    double_for_accidents.save()

    deductible_duration = ExtraData()
    deductible_duration.type_ = 'selection'
    deductible_duration.kind = 'option'
    deductible_duration.string = 'Franchise'
    deductible_duration.name = 'deductible_duration'
    deductible_duration.selection = '''30: 30 jours
60: 60 jours
90: 90 jours
'''
    deductible_duration.save()

    per_day_amount = ExtraData()
    per_day_amount.type_ = 'selection'
    per_day_amount.kind = 'option'
    per_day_amount.string = 'Indemnité journalière'
    per_day_amount.name = 'per_day_amount'
    per_day_amount.selection = '''50: 50 € par jour
100: 100 € par jour
150: 150 € par jour
'''
    per_day_amount.save()

    monthly_annuity = ExtraData()
    monthly_annuity.type_ = 'selection'
    monthly_annuity.kind = 'option'
    monthly_annuity.string = 'Rente mensuelle'
    monthly_annuity.name = 'monthly_annuity'
    monthly_annuity.selection = '''1000: 1000 € par mois
2000: 2000 € par mois
3000: 3000 € par mois
'''
    monthly_annuity.save()

    relapse_threshold = ExtraData()
    relapse_threshold.type_ = 'selection'
    relapse_threshold.kind = 'option'
    relapse_threshold.string = 'Durée avant rechute'
    relapse_threshold.name = 'relapse_threshold'
    relapse_threshold.selection = '''30: 30 jours
60: 60 jours
90: 90 jours
'''
    relapse_threshold.save()
    # }}}

    do_print('    Benefit')  # {{{
    salary_range_a = ExtraData()
    salary_range_a.type_ = 'numeric'
    salary_range_a.kind = 'benefit'
    salary_range_a.string = "Tranche A (année passée)"
    salary_range_a.name = 'salary_range_a'
    salary_range_a.save()

    salary_range_b = ExtraData()
    salary_range_b.type_ = 'numeric'
    salary_range_b.kind = 'benefit'
    salary_range_b.string = "Tranche B (année passée)"
    salary_range_b.name = 'salary_range_b'
    salary_range_b.save()

    salary_range_c = ExtraData()
    salary_range_c.type_ = 'numeric'
    salary_range_c.kind = 'benefit'
    salary_range_c.string = "Tranche C (année passée)"
    salary_range_c.name = 'salary_range_c'
    salary_range_c.save()

    salary_tax_rate = ExtraData()
    salary_tax_rate.type_ = 'numeric'
    salary_tax_rate.kind = 'benefit'
    salary_tax_rate.string = "Taux d'imposition du salaire net (%)"
    salary_tax_rate.name = 'salary_tax_rate'
    salary_tax_rate.save()

    salary_type = ExtraData()
    salary_type.type_ = 'selection'
    salary_type.kind = 'benefit'
    salary_type.string = 'Type de salaire'
    salary_type.name = 'salary_type'
    salary_type.selection = '''brut: Brut
net: Net
'''
    salary_type.default_value = 'net'
    salary_type.sub_datas.new()
    salary_type.sub_datas[-1].select_value = 'brut'
    salary_type.sub_datas[-1].child = salary_tax_rate
    salary_type.save()

    social_system_amount = ExtraData()
    social_system_amount.type_ = 'numeric'
    social_system_amount.kind = 'benefit'
    social_system_amount.string = \
        "Montant journalier remboursé par le système de santé"
    social_system_amount.name = 'social_system_amount'
    social_system_amount.save()

    children_in_care = ExtraData()
    children_in_care.type_ = 'integer'
    children_in_care.kind = 'benefit'
    children_in_care.string = "Nombre d'enfants à charge"
    children_in_care.name = 'children_in_care'
    children_in_care.save()
    # }}}

    do_print('\nFetching pre-configured rules')  # {{{
    option_age_eligibility_rule, = RuleEngine.find(
        [('short_name', '=', 'option_age_eligibility')])
    product_term_renewal_rule, = RuleEngine.find(
        [('short_name', '=', 'product_term_renewal_sync_sub_date')])
    # }}}

    do_print('\nCreating loan average rule')  # {{{
    loan_premium_rule = AverageLoanPremiumRule()
    loan_premium_rule.name = 'Règle de taux moyen prêt'
    loan_premium_rule.code = 'regle_taux_moyen_pret'
    loan_premium_rule.use_default_rule = True
    loan_premium_rule.default_fee_action = 'longest'
    loan_premium_rule.save()
    # }}}

    do_print('\nCreating Tables')  # {{{
    death_table = Table()
    death_table.name = 'TH-00-02'
    death_table.code = 'TH_00_02'
    death_table.type_ = 'numeric'
    death_table.number_of_digits = 5
    death_table.dimension_kind1 = 'value'
    death_table.dimension_name1 = 'Âge'
    death_table.dimension_order1 = 'alpha'
    for x in range(0, 111):
        death_table.dimension1.new()
        death_table.dimension1[-1].name = str(x)
        death_table.dimension1[-1].value = str(x)
        death_table.dimension1[-1].type = 'dimension1'
    death_table.save()

    death_table_dimensions = {x.value: x for x in death_table.dimension1}
    death_table_values = [
        100000, 99511, 99473, 99446, 99424, 99406, 99390, 99376, 99363, 99350,
        99338, 99325, 99312, 99296, 99276, 99250, 99213, 99163, 99097, 99015,
        98921, 98820, 98716, 98612, 98509, 98406, 98303, 98198, 98091, 97982,
        97870, 97756, 97639, 97517, 97388, 97249, 97100, 96939, 96765, 96576,
        96369, 96141, 95887, 95606, 95295, 94952, 94575, 94164, 93720, 93244,
        92736, 92196, 91621, 91009, 90358, 89665, 88929, 88151, 87329, 86460,
        85538, 84558, 83514, 82399, 81206, 79926, 78552, 77078, 75501, 73816,
        72019, 70105, 68070, 65914, 63637, 61239, 58718, 56072, 53303, 50411,
        47390, 44234, 40946, 37546, 34072, 30575, 27104, 23707, 20435, 17338,
        14464, 11852, 9526, 7498, 5769, 4331, 3166, 2249, 1549, 1032, 663,
        410, 244, 139, 75, 39, 19, 9, 4, 2, 1,
        ]
    for idx, value in enumerate(death_table_values):
        death_table.cells.new()
        death_table.cells[-1].value = str(value)
        death_table.cells[-1].dimension1 = death_table_dimensions[str(idx)]
    death_table.save()
    # }}}

    do_print('\nCreating commutation tables')  # {{{
    commutation = CommutationManager()
    commutation.lines.new()
    commutation.lines[0].rate = Decimal('0.025')
    commutation.lines[0].frequency = '12'
    commutation.lines[0].base_table = death_table
    commutation.save()
    commutation.lines[0].click('refresh')
    commutation.reload()
    test_commutation_table = commutation.lines[0].data_table.code
    # }}}

    do_print('\nCreating Rules')
    do_print('    Creating rule parameters')  # {{{
    # }}}

    do_print('    Creating tooling')  # {{{
    funeral_pure_premium_rule = RuleEngine()
    funeral_pure_premium_rule.context = rule_context
    funeral_pure_premium_rule.name = 'Prime pure obsèques'
    funeral_pure_premium_rule.short_name = 'prime_pure_obseques'
    funeral_pure_premium_rule.status = 'validated'
    funeral_pure_premium_rule.type_ = 'tool'
    funeral_pure_premium_rule.parameters.new()
    funeral_pure_premium_rule.parameters[0].string = 'Code table de mortalité'
    funeral_pure_premium_rule.parameters[0].name = 'code_table_mortalite'
    funeral_pure_premium_rule.parameters[0].type_ = 'char'
    funeral_pure_premium_rule.parameters.new()
    funeral_pure_premium_rule.parameters[1].string = 'Taux technique'
    funeral_pure_premium_rule.parameters[1].name = 'taux_technique'
    funeral_pure_premium_rule.parameters[1].type_ = 'numeric'
    funeral_pure_premium_rule.parameters[1].digits = 2
    funeral_pure_premium_rule.parameters.new()
    funeral_pure_premium_rule.parameters[2].string = 'Fractionnement'
    funeral_pure_premium_rule.parameters[2].name = 'fractionnement'
    funeral_pure_premium_rule.parameters[2].type_ = 'selection'
    funeral_pure_premium_rule.parameters[2].selection = '''1: Annuel
2: Semestriel
4: Trimestriel
12: Mensuel'''
    funeral_pure_premium_rule.parameters.new()
    funeral_pure_premium_rule.parameters[3].string = 'Capital'
    funeral_pure_premium_rule.parameters[3].name = 'capital'
    funeral_pure_premium_rule.parameters[3].type_ = 'numeric'
    funeral_pure_premium_rule.parameters[3].digits = 2
    funeral_pure_premium_rule.parameters.new()
    funeral_pure_premium_rule.parameters[4].string = 'Âge'
    funeral_pure_premium_rule.parameters[4].name = 'age'
    funeral_pure_premium_rule.parameters[4].type_ = 'integer'
    funeral_pure_premium_rule.algorithm = '''
table = param_code_table_mortalite()
taux = param_taux_technique()
fractionnement = param_fractionnement()
age = param_age()

Ax = commutation(table, taux, fractionnement, age, 'Ax')
ax = commutation(table, taux, fractionnement, age, 'a"x')

return param_capital() * Ax / ax
'''
    funeral_pure_premium_rule.save()

    funeral_provisions_rule = RuleEngine()
    funeral_provisions_rule.context = rule_context
    funeral_provisions_rule.name = 'Provisions mathématiques'
    funeral_provisions_rule.short_name = 'provisions_mathematiques'
    funeral_provisions_rule.status = 'validated'
    funeral_provisions_rule.type_ = 'tool'
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[0].string = 'Code table de mortalité'
    funeral_provisions_rule.parameters[0].name = 'code_table_mortalite'
    funeral_provisions_rule.parameters[0].type_ = 'char'
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[1].string = 'Taux technique'
    funeral_provisions_rule.parameters[1].name = 'taux_technique'
    funeral_provisions_rule.parameters[1].type_ = 'numeric'
    funeral_provisions_rule.parameters[1].digits = 2
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[2].string = 'Fractionnement'
    funeral_provisions_rule.parameters[2].name = 'fractionnement'
    funeral_provisions_rule.parameters[2].type_ = 'selection'
    funeral_provisions_rule.parameters[2].selection = '''1: Annuel
2: Semestriel
4: Trimestriel
12: Mensuel'''
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[3].string = 'Capital'
    funeral_provisions_rule.parameters[3].name = 'capital'
    funeral_provisions_rule.parameters[3].type_ = 'numeric'
    funeral_provisions_rule.parameters[3].digits = 2
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[4].string = 'Âge'
    funeral_provisions_rule.parameters[4].name = 'age'
    funeral_provisions_rule.parameters[4].type_ = 'integer'
    funeral_provisions_rule.parameters.new()
    funeral_provisions_rule.parameters[5].string = 'Date'
    funeral_provisions_rule.parameters[5].name = 'date'
    funeral_provisions_rule.parameters[5].type_ = 'date'
    funeral_provisions_rule.rules_used.append(
        RuleEngine(funeral_pure_premium_rule.id))
    funeral_provisions_rule.algorithm = '''
date = param_date()
table = param_code_table_mortalite()
taux = param_taux_technique()
fractionnement = param_fractionnement()
age_souscription = param_age()

if date_de_reduction() and date_de_reduction() <= date:
    base = valeur_reduite()
else:
    base = param_capital()

prime = rule_prime_pure_obseques(code_table_mortalite=table,
    taux_technique=taux, fractionnement=fractionnement, capital=base,
    age=age_souscription)

# Pour lisser entre les deux annees
annees_ecoulees = annees_entre(date_effet_initiale_contrat(), date)
mois_ecoules = mois_entre(ajouter_annees(date_effet_initiale_contrat(),
        annees_ecoulees), date)

age = age_souscription + annees_ecoulees

Ax = commutation(table, taux, fractionnement, age, 'Ax')
Ax1 = commutation(table, taux, fractionnement, age + 1, 'Ax')
ax = commutation(table, taux, fractionnement, age, 'a"x')
ax1 = commutation(table, taux, fractionnement, age + 1, 'a"x')

v1 = base * Ax - prime * ax
v2 = base * Ax1 - prime * ax1

return max(mois_ecoules / 12.0 * (v2 - v1) + v1, 0.0)
'''
    funeral_provisions_rule.save()
    # }}}

    do_print('    Creating coverage amount rules')  # {{{
    coverage_amount_rule = RuleEngine()
    coverage_amount_rule.context = rule_context
    coverage_amount_rule.name = 'Montants de couverture possibles'
    coverage_amount_rule.short_name = 'montants_de_couverture_possibles'
    coverage_amount_rule.status = 'validated'
    coverage_amount_rule.type_ = 'coverage_amount_selection'
    coverage_amount_rule.parameters.new()
    coverage_amount_rule.parameters[0].string = 'Minimum'
    coverage_amount_rule.parameters[0].name = 'minimum_amount'
    coverage_amount_rule.parameters[0].type_ = 'integer'
    coverage_amount_rule.parameters.new()
    coverage_amount_rule.parameters[1].string = 'Maximum'
    coverage_amount_rule.parameters[1].name = 'maximum_amount'
    coverage_amount_rule.parameters[1].type_ = 'integer'
    coverage_amount_rule.parameters.new()
    coverage_amount_rule.parameters[2].string = 'Écart entre les valeurs'
    coverage_amount_rule.parameters[2].name = 'amount_step'
    coverage_amount_rule.parameters[2].type_ = 'integer'
    coverage_amount_rule.algorithm = '''
minimum = param_minimum_amount()
maximum = param_maximum_amount()
step = param_amount_step()

assert minimum
assert maximum
assert step
assert minimum <= maximum
assert step > 0

result = []
valeur = minimum

while valeur <= maximum:
    result.append(valeur)
    valeur += step

return result
'''
    coverage_amount_rule.save()
    # }}}

    do_print('    Creating rating rules')  # {{{
    responsability_rating_rule = RuleEngine()
    responsability_rating_rule.context = rule_context
    responsability_rating_rule.name = 'Tarif de garantie responsabilité civile'
    responsability_rating_rule.short_name = \
        'tarif_garantie_responsabilite_civile'
    responsability_rating_rule.status = 'validated'
    responsability_rating_rule.type_ = 'premium'
    responsability_rating_rule.extra_data_used.append(
        ExtraData(house_rooms.id))
    responsability_rating_rule.extra_data_used.append(
        ExtraData(house_construction_date.id))
    responsability_rating_rule.algorithm = '''
return compl_house_rooms() * 10.5 + compl_house_construction_date() / 500.0
'''
    responsability_rating_rule.save()

    fire_rating_rule = RuleEngine()
    fire_rating_rule.context = rule_context
    fire_rating_rule.name = 'Tarif de garantie incendie'
    fire_rating_rule.short_name = 'tarif_garantie_incendie'
    fire_rating_rule.status = 'validated'
    fire_rating_rule.type_ = 'premium'
    fire_rating_rule.extra_data_used.append(ExtraData(fire_damage_limit.id))
    fire_rating_rule.extra_data_used.append(ExtraData(electrical_fires.id))
    fire_rating_rule.extra_data_used.append(ExtraData(house_size.id))
    fire_rating_rule.extra_data_used.append(
        ExtraData(house_construction_date.id))
    fire_rating_rule.algorithm = '''
electrical = 1.0
if compl_electrical_fires():
    electrical = 1.5

return int(compl_fire_damage_limit()) * electrical / 10 * (
    1 + compl_house_size() / 100.0 +
    (2100 - compl_house_construction_date()) / 100.0)
'''
    fire_rating_rule.save()

    death_rating_rule = RuleEngine()
    death_rating_rule.context = rule_context
    death_rating_rule.name = 'Tarif de garantie décès'
    death_rating_rule.short_name = 'tarif_garantie_deces'
    death_rating_rule.status = 'validated'
    death_rating_rule.type_ = 'premium'
    death_rating_rule.extra_data_used.append(ExtraData(job_category.id))
    death_rating_rule.extra_data_used.append(
        ExtraData(double_for_accidents.id))
    death_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.23,
    'csp3': 1.79,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = montant_de_couverture() / 1000.0
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
age_coeff = ((age + 30) / 110.0) ** 2 + 0.5
acc_coeff = 1.5 if compl_double_for_accidents() else 1.0

return base * csp_coeff * age_coeff * acc_coeff
'''
    death_rating_rule.save()

    unemployment_rating_rule = RuleEngine()
    unemployment_rating_rule.context = rule_context
    unemployment_rating_rule.name = 'Tarif de garantie incapacité'
    unemployment_rating_rule.short_name = 'tarif_garantie_incapacite'
    unemployment_rating_rule.status = 'validated'
    unemployment_rating_rule.type_ = 'premium'
    unemployment_rating_rule.extra_data_used.append(ExtraData(job_category.id))
    unemployment_rating_rule.extra_data_used.append(
        ExtraData(deductible_duration.id))
    unemployment_rating_rule.extra_data_used.append(
        ExtraData(per_day_amount.id))
    unemployment_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.64,
    'csp3': 2.61,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = int(compl_per_day_amount())
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
age_coeff = ((age + 30) / 110.0) ** 2 + 0.5
deductible_coeff = (200 - int(compl_deductible_duration())) / 200.0

return base * csp_coeff * age_coeff * deductible_coeff
'''
    unemployment_rating_rule.save()

    disability_rating_rule = RuleEngine()
    disability_rating_rule.context = rule_context
    disability_rating_rule.name = 'Tarif de garantie invalidité'
    disability_rating_rule.short_name = 'tarif_garantie_invalidite'
    disability_rating_rule.status = 'validated'
    disability_rating_rule.type_ = 'premium'
    disability_rating_rule.extra_data_used.append(ExtraData(job_category.id))
    disability_rating_rule.extra_data_used.append(
        ExtraData(monthly_annuity.id))
    disability_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.64,
    'csp3': 2.61,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = int(compl_monthly_annuity()) / 312.4
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
age_coeff = -((age - 50) / 200.0) ** 2 + 2

return base * csp_coeff * age_coeff
'''
    disability_rating_rule.save()

    loan_death_rating_rule = RuleEngine()
    loan_death_rating_rule.context = rule_context
    loan_death_rating_rule.name = 'Tarif de garantie décès emprunteur'
    loan_death_rating_rule.short_name = 'tarif_garantie_deces_emprunteur'
    loan_death_rating_rule.status = 'validated'
    loan_death_rating_rule.type_ = 'premium'
    loan_death_rating_rule.extra_data_used.append(ExtraData(job_category.id))
    loan_death_rating_rule.extra_data_used.append(
        ExtraData(co_borrower_relation.id))
    loan_death_rating_rule.extra_data_used.append(
        ExtraData(reduction_libre.id))
    loan_death_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.23,
    'csp3': 1.79,
}
RELATION_MODIFICATEUR = {
    'aucune': 1.0,
    'mariage': 0.7,
    'pacs': 0.8,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = montant_du_pret() / 10000.0 * quotite()
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
age_coeff = ((age + 30) / 110.0) ** 2 + 0.5
rel_coeff = RELATION_MODIFICATEUR[compl_co_borrower_relation()]
reduc_coeff = (1 - int(compl_reduction_libre() or '0') / 100.0)

return base * csp_coeff * age_coeff * rel_coeff * reduc_coeff
'''
    loan_death_rating_rule.save()

    loan_unemployment_rating_rule = RuleEngine()
    loan_unemployment_rating_rule.context = rule_context
    loan_unemployment_rating_rule.name = \
        'Tarif de garantie incapacité emprunteur'
    loan_unemployment_rating_rule.short_name = \
        'tarif_garantie_incapacite_emprunteur'
    loan_unemployment_rating_rule.status = 'validated'
    loan_unemployment_rating_rule.type_ = 'premium'
    loan_unemployment_rating_rule.extra_data_used.append(
        ExtraData(job_category.id))
    loan_unemployment_rating_rule.extra_data_used.append(
        ExtraData(deductible_duration.id))
    loan_unemployment_rating_rule.extra_data_used.append(
        ExtraData(co_borrower_relation.id))
    loan_unemployment_rating_rule.extra_data_used.append(
        ExtraData(reduction_libre.id))
    loan_unemployment_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.64,
    'csp3': 2.61,
}
RELATION_MODIFICATEUR = {
    'aucune': 1.0,
    'mariage': 0.7,
    'pacs': 0.8,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = 0.01 * montant_du_pret() / duree_pret_en_mois() * quotite()
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
deductible_coeff = (200 - int(compl_deductible_duration())) / 200.0
age_coeff = ((age + 30) / 110.0) ** 2 + 0.5
rel_coeff = RELATION_MODIFICATEUR[compl_co_borrower_relation()]
reduc_coeff = (1 - int(compl_reduction_libre() or '0') / 100.0)

return base * csp_coeff * age_coeff * rel_coeff * deductible_coeff * reduc_coeff
'''
    loan_unemployment_rating_rule.save()

    loan_disability_rating_rule = RuleEngine()
    loan_disability_rating_rule.context = rule_context
    loan_disability_rating_rule.name = \
        'Tarif de garantie invalidité emprunteur'
    loan_disability_rating_rule.short_name = \
        'tarif_garantie_invalidite_emprunteur'
    loan_disability_rating_rule.status = 'validated'
    loan_disability_rating_rule.type_ = 'premium'
    loan_disability_rating_rule.extra_data_used.append(
        ExtraData(job_category.id))
    loan_disability_rating_rule.extra_data_used.append(
        ExtraData(co_borrower_relation.id))
    loan_disability_rating_rule.extra_data_used.append(
        ExtraData(reduction_libre.id))
    loan_disability_rating_rule.algorithm = '''
CSP_MODIFICATEUR = {
    'csp1': 1.0,
    'csp2': 1.64,
    'csp3': 2.61,
}
RELATION_MODIFICATEUR = {
    'aucune': 1.0,
    'mariage': 0.7,
    'pacs': 0.8,
}

age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = 0.01 * montant_du_pret() / duree_pret_en_mois() * quotite()
csp_coeff = CSP_MODIFICATEUR[compl_job_category()]
age_coeff = -((age - 50) / 200.0) ** 2 + 2
rel_coeff = RELATION_MODIFICATEUR[compl_co_borrower_relation()]
reduc_coeff = (1 - int(compl_reduction_libre() or '0') / 100.0)

return base * csp_coeff * age_coeff * rel_coeff * reduc_coeff
'''
    loan_disability_rating_rule.save()

    funeral_rating_rule = RuleEngine()
    funeral_rating_rule.context = rule_context
    funeral_rating_rule.name = 'Tarif Obsèques'
    funeral_rating_rule.short_name = 'tarif_obseques'
    funeral_rating_rule.status = 'validated'
    funeral_rating_rule.type_ = 'premium'
    funeral_rating_rule.rules_used.append(
        RuleEngine(funeral_pure_premium_rule.id))
    funeral_rating_rule.algorithm = '''
TABLE_MORTALITE = 'TH_00_02'
FRACTIONNEMENT = '12'  # mensuel
TAUX_TECHNIQUE = 0.025  # 2.5 %
TAUX_CHARGEMENT = 0.215

capital = montant_de_couverture()
age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = rule_prime_pure_obseques(code_table_mortalite=TABLE_MORTALITE,
    taux_technique=TAUX_TECHNIQUE, fractionnement=FRACTIONNEMENT,
    capital=capital, age=age)

return base * (1 + TAUX_CHARGEMENT)
'''
    funeral_rating_rule.save()
    # }}}

    do_print('    Creating surrender rules')  # {{{
    funeral_surrender_rule = RuleEngine()
    funeral_surrender_rule.context = rule_context
    funeral_surrender_rule.name = 'Rachat Obsèques'
    funeral_surrender_rule.short_name = 'rachat_obseques'
    funeral_surrender_rule.status = 'validated'
    funeral_surrender_rule.type_ = 'surrender'
    funeral_surrender_rule.rules_used.append(
        RuleEngine(funeral_provisions_rule.id))
    funeral_surrender_rule.algorithm = '''
TABLE_MORTALITE = 'TH_00_02'
FRACTIONNEMENT = '12'  # mensuel
TAUX_TECHNIQUE = 0.025  # 2.5 %
FRAIS_RACHAT = 0.1

date = date_de_calcul()
capital = montant_de_couverture()
age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = rule_provisions_mathematiques(code_table_mortalite=TABLE_MORTALITE,
    taux_technique=TAUX_TECHNIQUE, fractionnement=FRACTIONNEMENT,
    capital=capital, age=age, date=date)

return arrondir(base * (1 + FRAIS_RACHAT), 0.01)
'''
    funeral_surrender_rule.save()
    # }}}

    do_print('    Creating surrender eligibility rules')  # {{{
    funeral_surrender_eligibility_rule = RuleEngine()
    funeral_surrender_eligibility_rule.context = rule_context
    funeral_surrender_eligibility_rule.name = 'Éligibilité rachat Obsèques'
    funeral_surrender_eligibility_rule.short_name = \
        'eligibilite_rachat_obseques'
    funeral_surrender_eligibility_rule.status = 'validated'
    funeral_surrender_eligibility_rule.type_ = 'surrender_eligibility'
    funeral_surrender_eligibility_rule.parameters.new()
    funeral_surrender_eligibility_rule.parameters[0].string = \
        "Nombre d'années depuis la souscription"
    funeral_surrender_eligibility_rule.parameters[0].name = 'nombre_annees'
    funeral_surrender_eligibility_rule.parameters[0].type_ = 'integer'
    funeral_surrender_eligibility_rule.parameters.new()
    funeral_surrender_eligibility_rule.parameters[1].string = \
        "Vérifier la date de dernier paiement"
    funeral_surrender_eligibility_rule.parameters[1].name = \
        'verification_paiement'
    funeral_surrender_eligibility_rule.parameters[1].type_ = 'boolean'
    funeral_surrender_eligibility_rule.algorithm = '''
date = date_de_calcul()
nombre_annees = param_nombre_annees()

result = True
if not date_de_reduction() and  param_verification_paiement():
    if date_fin_derniere_quittance_payee() < date:
        ajouter_erreur(u'La date de rachat ne peut être inférieure à la date '
            u'de fin de la dernière quittance payée (%s)' %
            date_fin_derniere_quittance_payee())
        result = False

assert nombre_annees and nombre_annees >= 0, \\
    "Nombre d'années doit être positif"

if annees_entre(date_effet_initiale_contrat(), date) < nombre_annees:
    ajouter_erreur(u"Le rachat ne sera possible qu'après %i année(s) suite "
        u"à la souscription" % nombre_annees)
    result = False

return result
'''
    funeral_surrender_eligibility_rule.save()
    # }}}

    do_print('    Creating reduction rules')  # {{{
    funeral_reduction_rule = RuleEngine()
    funeral_reduction_rule.context = rule_context
    funeral_reduction_rule.name = 'Mise en réduction Obsèques'
    funeral_reduction_rule.short_name = 'reduction_obseques'
    funeral_reduction_rule.status = 'validated'
    funeral_reduction_rule.type_ = 'reduction'
    funeral_reduction_rule.rules_used.append(
        RuleEngine(funeral_provisions_rule.id))
    funeral_reduction_rule.algorithm = '''
TABLE_MORTALITE = 'TH_00_02'
FRACTIONNEMENT = '12'  # mensuel
TAUX_TECHNIQUE = 0.025  # 2.5 %

date = date_de_calcul()
capital = montant_de_couverture()
age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())

base = rule_provisions_mathematiques(code_table_mortalite=TABLE_MORTALITE,
    taux_technique=TAUX_TECHNIQUE, fractionnement=FRACTIONNEMENT,
    capital=capital, age=age, date=date)

return arrondir(base / commutation(TABLE_MORTALITE, TAUX_TECHNIQUE,
        FRACTIONNEMENT, annees_entre(date_de_naissance(), date_de_calcul()),
        'Ax'), 0.01)
'''
    funeral_reduction_rule.save()
    # }}}

    do_print('    Creating reduction eligibility rules')  # {{{
    funeral_reduction_eligibility_rule = RuleEngine()
    funeral_reduction_eligibility_rule.context = rule_context
    funeral_reduction_eligibility_rule.name = \
        'Éligibilité mise en réduction Obsèques'
    funeral_reduction_eligibility_rule.short_name = \
        'eligibilite_reduction_obseques'
    funeral_reduction_eligibility_rule.status = 'validated'
    funeral_reduction_eligibility_rule.type_ = 'reduction_eligibility'
    funeral_reduction_eligibility_rule.parameters.new()
    funeral_reduction_eligibility_rule.parameters[0].string = \
        "Nombre d'années depuis la souscription"
    funeral_reduction_eligibility_rule.parameters[0].name = 'nombre_annees'
    funeral_reduction_eligibility_rule.parameters[0].type_ = 'integer'
    funeral_reduction_eligibility_rule.parameters.new()
    funeral_reduction_eligibility_rule.parameters[1].string = \
        "Vérifier la date de dernier paiement"
    funeral_reduction_eligibility_rule.parameters[1].name = \
        'verification_paiement'
    funeral_reduction_eligibility_rule.parameters[1].type_ = 'boolean'
    funeral_reduction_eligibility_rule.algorithm = '''
date = date_de_calcul()
nombre_annees = param_nombre_annees()

result = True
if date_de_reduction():
    ajouter_erreur(u'Le contrat est déjà réduit !')
    return False

if param_verification_paiement():
    derniere_quittance = date_fin_derniere_quittance_payee()
    if not derniere_quittance or derniere_quittance < date:
        ajouter_erreur(u'La date de rachat ne peut être inférieure à la date '
            u'de fin de la dernière quittance payée (%s)' %
            date_fin_derniere_quittance_payee())
        result = False

assert nombre_annees and nombre_annees >= 0, \\
    "Nombre d'années doit être positif"

if annees_entre(date_effet_initiale_contrat(), date) < nombre_annees:
    ajouter_erreur(u"Le rachat ne sera possible qu'après %i année(s) suite "
        u"à la souscription" % nombre_annees)
    result = False

return result
'''
    funeral_reduction_eligibility_rule.save()
    # }}}

    do_print('    Creating details rules')  # {{{
    funeral_details_rule = RuleEngine()
    funeral_details_rule.context = rule_context
    funeral_details_rule.name = 'Détails de garantie obsèques'
    funeral_details_rule.short_name = 'details_obseques'
    funeral_details_rule.status = 'validated'
    funeral_details_rule.type_ = 'option_extra_detail'
    funeral_details_rule.rules_used.append(
        RuleEngine(funeral_surrender_rule.id))
    funeral_details_rule.rules_used.append(
        RuleEngine(funeral_reduction_rule.id))
    funeral_details_rule.rules_used.append(
        RuleEngine(funeral_provisions_rule.id))
    funeral_details_rule.algorithm = '''
reduit = date_de_reduction()

if not montant_de_couverture():
    return {
        'valeur_rachat': 0.00,
        'valeur_reduction': 0.00,
        }

rachat = rule_rachat_obseques()
if not reduit or reduit < date_de_calcul():
    reduction = rule_reduction_obseques()
else:
    reduction = 0.0

return {
    'valeur_rachat': arrondir(rachat, 0.01),
    'valeur_reduction': arrondir(reduction, 0.01),
    }
'''
    funeral_details_rule.save()
    # }}}

    do_print('    Creating benefit eligibility rules')  # {{{
    capital_eligibility_rule = RuleEngine()
    capital_eligibility_rule.context = rule_context
    capital_eligibility_rule.name = 'Éligibilité capital'
    capital_eligibility_rule.short_name = 'capital_eligibility'
    capital_eligibility_rule.status = 'validated'
    capital_eligibility_rule.type_ = 'benefit'
    capital_eligibility_rule.algorithm = '''
date_declaration = date_declaration_sinistre()
date_debut_prejudice = date_de_debut_du_prejudice()

if date_declaration > ajouter_mois(date_debut_prejudice, 3):
    ajouter_info(u"Délai de saisi dépassé, veuillez être plus réactif "
        u"à l'avenir")
    return False

if code_de_l_evenement_du_prejudice() == 'suicide':
    if ajouter_annees(date_effet_initiale_contrat(), 1) < date_debut_prejudice:
        return True
    ajouter_info(u"Un suicide n'est pas éligible au versement d'un capital "
        u"au cours de la première année")
    return False

return True
'''
    capital_eligibility_rule.save()

    benefit_eligibility_rule = RuleEngine()
    benefit_eligibility_rule.context = rule_context
    benefit_eligibility_rule.name = 'Éligibilité prestation'
    benefit_eligibility_rule.short_name = 'benefit_eligibility'
    benefit_eligibility_rule.status = 'validated'
    benefit_eligibility_rule.type_ = 'benefit'
    benefit_eligibility_rule.algorithm = '''
date_declaration = date_declaration_sinistre()
date_debut_prejudice = date_de_debut_du_prejudice()

if date_declaration > ajouter_mois(date_debut_prejudice, 3):
    ajouter_info(u"Délai de saisi dépassé, veuillez être plus réactif "
        u"à l'avenir")
    return False

if est_une_rechute():
    date_max_rechute = ajouter_jours(date_fin_dernier_prejudice(),
        int(compl_relapse_threshold()))
    if date_debut_prejudice > date_max_rechute:
        ajouter_info(u"Délai dépassé pour une rechute, veuillez créer un "
            u"nouveau dossier")
        return False
return True
'''
    benefit_eligibility_rule.extra_data_used.append(
        ExtraData(relapse_threshold.id))
    benefit_eligibility_rule.save()
    # }}}

    do_print('    Creating benefit deductible rules')  # {{{
    benefit_deductible_rule = RuleEngine()
    benefit_deductible_rule.context = rule_context
    benefit_deductible_rule.name = 'Franchise en nombre de jours'
    benefit_deductible_rule.short_name = 'benefit_deductible'
    benefit_deductible_rule.status = 'validated'
    benefit_deductible_rule.type_ = 'benefit_deductible'
    benefit_deductible_rule.parameters.new()
    benefit_deductible_rule.parameters[0].string = 'Nombre de jours'
    benefit_deductible_rule.parameters[0].name = 'number_of_days'
    benefit_deductible_rule.parameters[0].type_ = 'integer'
    benefit_deductible_rule.algorithm = '''
date_prejudice = date_de_debut_du_prejudice()
if est_une_rechute():
    return ajouter_jours(date_prejudice,  -1)

return ajouter_jours(date_prejudice, param_number_of_days())
'''
    benefit_deductible_rule.extra_data_used.append(
        ExtraData(relapse_threshold.id))
    benefit_deductible_rule.save()
    # }}}

    do_print('    Creating benefit amount rules')  # {{{
    benefit_capital_rule = RuleEngine()
    benefit_capital_rule.context = rule_context
    benefit_capital_rule.name = 'Capital Assuré'
    benefit_capital_rule.short_name = 'benefit_capital'
    benefit_capital_rule.status = 'validated'
    benefit_capital_rule.type_ = 'benefit'
    benefit_capital_rule.algorithm = '''
date_debut_periode = date_debut_periode_indemnisation()
base = montant_de_couverture()

return [{
        'start_date': date_debut_periode,
        'end_date': None,
        'nb_of_unit': 1,
        'unit': 'day',
        'amount': base,
        'base_amount': base,
        'amount_per_unit': base,
        }]
'''
    benefit_capital_rule.save()

    benefit_simple_value_rule = RuleEngine()
    benefit_simple_value_rule.context = rule_context
    benefit_simple_value_rule.name = 'Montant forfaitaire'
    benefit_simple_value_rule.short_name = 'benefit_simple_value'
    benefit_simple_value_rule.status = 'validated'
    benefit_simple_value_rule.type_ = 'benefit'
    benefit_simple_value_rule.parameters.new()
    benefit_simple_value_rule.parameters[0].string = \
        'Montant du forfait (par jours)'
    benefit_simple_value_rule.parameters[0].name = 'flat_daily_amount'
    benefit_simple_value_rule.parameters[0].type_ = 'numeric'
    benefit_simple_value_rule.parameters[0].digits = 2
    benefit_simple_value_rule.algorithm = '''
date_debut_periode = date_debut_periode_indemnisation()
date_fin_periode = date_fin_periode_indemnisation()
base = param_flat_daily_amount()

return [{
        'start_date': date_debut_periode,
        'end_date': date_fin_periode,
        'nb_of_unit': (date_fin_periode - date_debut_periode).days + 1,
        'unit': 'day',
        'amount': base * ((date_fin_periode - date_debut_periode).days + 1),
        'base_amount': base,
        'amount_per_unit': base,
        }]
'''
    benefit_simple_value_rule.save()

    benefit_complex_value_rule = RuleEngine()
    benefit_complex_value_rule.context = rule_context
    benefit_complex_value_rule.name = 'Maintien du salaire'
    benefit_complex_value_rule.short_name = 'benefit_complex_value'
    benefit_complex_value_rule.status = 'validated'
    benefit_complex_value_rule.type_ = 'benefit'
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(salary_range_a.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(salary_range_b.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(salary_range_c.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(salary_type.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(salary_tax_rate.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(social_system_amount.id))
    benefit_complex_value_rule.extra_data_used.append(
        ExtraData(children_in_care.id))
    benefit_complex_value_rule.parameters.new()
    benefit_complex_value_rule.parameters[0].string = 'Taux tranche A (%)'
    benefit_complex_value_rule.parameters[0].name = 'range_a_rate'
    benefit_complex_value_rule.parameters[0].type_ = 'integer'
    benefit_complex_value_rule.parameters.new()
    benefit_complex_value_rule.parameters[1].string = 'Taux tranche B (%)'
    benefit_complex_value_rule.parameters[1].name = 'range_b_rate'
    benefit_complex_value_rule.parameters[1].type_ = 'integer'
    benefit_complex_value_rule.parameters.new()
    benefit_complex_value_rule.parameters[2].string = 'Taux tranche C (%)'
    benefit_complex_value_rule.parameters[2].name = 'range_c_rate'
    benefit_complex_value_rule.parameters[2].type_ = 'integer'
    benefit_complex_value_rule.algorithm = '''
CHILDREN_RATIO = {
    1: 0.8,
    2: 1,
    3: 1.1,
    }

date_debut_periode = date_debut_periode_indemnisation()
date_fin_periode = date_fin_periode_indemnisation()

base = compl_salary_range_a() * param_range_a_rate() / 100.0
base += compl_salary_range_b() * param_range_b_rate() / 100.0
base += compl_salary_range_c() * param_range_c_rate() / 100.0

if compl_salary_type() == 'brut':
    base = base / (1 - compl_salary_tax_rate() / 100.0)

children = max(min(compl_children_in_care(), 3), 1)
base = children * CHILDREN_RATIO[children]

daily_base = base / 365.0
already_paid = compl_social_system_amount()
remaining = max(daily_base - already_paid, 0.0)

return [{
        'start_date': date_debut_periode,
        'end_date': date_fin_periode,
        'nb_of_unit': (date_fin_periode - date_debut_periode).days + 1,
        'unit': 'day',
        'amount': base * ((date_fin_periode - date_debut_periode).days + 1),
        'base_amount': base,
        'amount_per_unit': base,
        }]
'''
    benefit_complex_value_rule.save()
    # }}}

    do_print('    Creating underwriting rules')  # {{{
    underwriting_rule = RuleEngine()
    underwriting_rule.context = rule_context
    underwriting_rule.name = 'Analyse de risque base CSP'
    underwriting_rule.short_name = 'analyse_de_risque_csp'
    underwriting_rule.status = 'validated'
    underwriting_rule.type_ = 'underwriting'
    underwriting_rule.extra_data_used.append(ExtraData(job_category.id))
    underwriting_rule.algorithm = '''
job_category = compl_job_category()
if job_category == 'csp1':
    return True
elif job_category == 'csp2':
    age = annees_entre(date_de_naissance(), date_effet_initiale_contrat())
    return age <= 60
else:
    return False
'''
    underwriting_rule.save()
    # }}}

    do_print('\nCreating End of Coverage Motives')  # {{{
    left_reason = CoveredEndReason()
    left_reason.code = 'demission'
    left_reason.name = 'Démission'
    left_reason.save()

    fired_reason = CoveredEndReason()
    fired_reason.code = 'licensiement'
    fired_reason.name = 'Licensiement'
    fired_reason.save()

    sell_reason = CoveredEndReason()
    sell_reason.code = 'revente'
    sell_reason.name = 'Revente'
    sell_reason.save()
    # }}}

    do_print('\nCreating Underwriting Decisions')  # {{{
    contract_accepted = UnderwritingDecision()
    contract_accepted.name = 'Acceptation sans conditions'
    contract_accepted.code = 'contract_fully_accepted'
    contract_accepted.level = 'contract'
    contract_accepted.status = 'accepted'
    contract_accepted.decline_option = False
    contract_accepted.with_extra_data = True
    contract_accepted.save()

    contract_accepted_conditions = UnderwritingDecision()
    contract_accepted_conditions.name = 'Acceptation sous conditions'
    contract_accepted_conditions.code = 'contract_accepted_with_conditions'
    contract_accepted_conditions.level = 'contract'
    contract_accepted_conditions.status = 'accepted_with_conditions'
    contract_accepted_conditions.decline_option = False
    contract_accepted_conditions.save()

    contract_denied = UnderwritingDecision()
    contract_denied.name = 'Refus'
    contract_denied.code = 'contract_denied'
    contract_denied.level = 'contract'
    contract_denied.status = 'denied'
    contract_denied.decline_option = True
    contract_denied.save()

    contract_pending = UnderwritingDecision()
    contract_pending.name = 'En attente'
    contract_pending.code = 'contract_pending'
    contract_pending.level = 'contract'
    contract_pending.status = 'pending'
    contract_pending.decline_option = True
    contract_pending.save()

    option_accepted = UnderwritingDecision()
    option_accepted.name = 'Acceptation sans conditions'
    option_accepted.code = 'coverage_fully_accepted'
    option_accepted.level = 'coverage'
    option_accepted.status = 'accepted'
    option_accepted.decline_option = False
    option_accepted.contract_decisions.append(
        UnderwritingDecision(contract_accepted.id))
    option_accepted.save()

    option_accepted_conditions = UnderwritingDecision()
    option_accepted_conditions.name = 'Acceptation sous conditions'
    option_accepted_conditions.code = 'coverage_accepted_with_conditions'
    option_accepted_conditions.level = 'coverage'
    option_accepted_conditions.status = 'accepted_with_conditions'
    option_accepted_conditions.decline_option = False
    option_accepted_conditions.contract_decisions.append(
        UnderwritingDecision(contract_accepted_conditions.id))
    option_accepted_conditions.save()

    option_denied = UnderwritingDecision()
    option_denied.name = 'Refus'
    option_denied.code = 'coverage_denied'
    option_denied.level = 'coverage'
    option_denied.status = 'denied'
    option_denied.decline_option = True
    option_denied.contract_decisions.append(
        UnderwritingDecision(contract_denied.id))
    option_denied.save()

    option_pending = UnderwritingDecision()
    option_pending.name = 'En attente'
    option_pending.code = 'coverage_pending'
    option_pending.level = 'coverage'
    option_pending.status = 'pending'
    option_pending.decline_option = True
    option_pending.contract_decisions.append(
        UnderwritingDecision(contract_pending.id))
    option_pending.save()
    # }}}

    do_print('\nSetting product configuration')  # {{{
    product_config = ProductConfiguration(1)
    product_config.loan_number_sequence = loan_sequence
    product_config.save()
    claim_config = ClaimConfiguration(1)
    claim_config.payment_journal, = PaymentJournal.find(
        [('name', '=', 'Sepa')])
    claim_config.prest_ij_sequence = prest_ij_sequence
    claim_config.prest_ij_period_sequence = prest_ij_period_sequence
    claim_config.claim_default_payment_term, = PaymentTerm.find(
        [('name', '=', 'Par défaut')])
    claim_config.save()
    # }}}

    do_print('\nCreating Event Descs')  # {{{
    illness_event = EventDesc()
    illness_event.code = 'illness'
    illness_event.name = 'Maladie'
    illness_event.save()

    work_illness_event = EventDesc()
    work_illness_event.code = 'work_illness'
    work_illness_event.name = 'Maladie professionnelle'
    work_illness_event.save()

    accident_event = EventDesc()
    accident_event.code = 'accident'
    accident_event.name = 'Accident'
    accident_event.save()

    work_accident_event = EventDesc()
    work_accident_event.code = 'work_accident'
    work_accident_event.name = 'Accident du travail'
    work_accident_event.save()

    pregnancy_event = EventDesc()
    pregnancy_event.code = 'pregnancy'
    pregnancy_event.name = 'Grossesse'
    pregnancy_event.save()

    suicide_event = EventDesc()
    suicide_event.code = 'suicide'
    suicide_event.name = 'Suicide'
    suicide_event.save()
    # }}}

    do_print('\nCreating Claim Closing Reasons')  # {{{
    death_reason = ClaimClosingReason()
    death_reason.code = 'death'
    death_reason.name = 'Décès'
    death_reason.save()

    back_to_work_reason = ClaimClosingReason()
    back_to_work_reason.code = 'back_to_work'
    back_to_work_reason.name = 'Reprise du travail'
    back_to_work_reason.save()

    invalidity_reason = ClaimClosingReason()
    invalidity_reason.code = 'invalidity'
    invalidity_reason.name = 'Passage en invalidité'
    invalidity_reason.save()
    # }}}

    do_print('\nCreating Claim Eligibility Decision')  # {{{
    automatically_accepted = BenefitEligibilityDecision()
    automatically_accepted.code = 'automatically_accepted'
    automatically_accepted.name = 'Acceptation automatique'
    automatically_accepted.state = 'accepted'
    automatically_accepted.save()

    automatically_refused = BenefitEligibilityDecision()
    automatically_refused.code = 'automatically_refused'
    automatically_refused.name = 'Refus automatique'
    automatically_refused.state = 'refused'
    automatically_refused.save()
    # }}}

    do_print('\nCreating Loss Descs')  # {{{
    death = LossDesc()
    death.code = 'death'
    death.name = 'Décès'
    death.kind = 'person'
    death.loss_kind = 'death'
    death.has_end_date = False
    death.event_descs.append(EventDesc(illness_event.id))
    death.event_descs.append(EventDesc(accident_event.id))
    death.event_descs.append(EventDesc(suicide_event.id))
    death.closing_reasons.append(
        ClaimClosingReason(death_reason.id))
    death.save()

    death_claim_process.for_loss_descs.append(LossDesc(death.id))
    death_claim_process.save()

    work_interruption = LossDesc()
    work_interruption.code = 'temporary_work_interruption'
    work_interruption.name = 'Arrêt de travail'
    work_interruption.kind = 'person'
    work_interruption.loss_kind = 'std'
    work_interruption.has_end_date = True
    work_interruption.event_descs.append(EventDesc(illness_event.id))
    work_interruption.event_descs.append(EventDesc(work_illness_event.id))
    work_interruption.event_descs.append(EventDesc(accident_event.id))
    work_interruption.event_descs.append(EventDesc(work_accident_event.id))
    work_interruption.event_descs.append(EventDesc(pregnancy_event.id))
    work_interruption.closing_reasons.append(
        ClaimClosingReason(death_reason.id))
    work_interruption.closing_reasons.append(
        ClaimClosingReason(back_to_work_reason.id))
    work_interruption.closing_reasons.append(
        ClaimClosingReason(invalidity_reason.id))
    work_interruption.save()

    work_interruption_claim_process.for_loss_descs.append(
        LossDesc(work_interruption.id))
    work_interruption_claim_process.save()

    validity_loss = LossDesc()
    validity_loss.code = 'temporary_validity_loss'
    validity_loss.name = 'Invalidité'
    validity_loss.kind = 'person'
    validity_loss.loss_kind = 'ltd'
    validity_loss.has_end_date = True
    validity_loss.event_descs.append(EventDesc(illness_event.id))
    validity_loss.event_descs.append(EventDesc(work_illness_event.id))
    validity_loss.event_descs.append(EventDesc(accident_event.id))
    validity_loss.event_descs.append(EventDesc(work_accident_event.id))
    validity_loss.closing_reasons.append(
        ClaimClosingReason(death_reason.id))
    validity_loss.save()
    # }}}

    do_print('\nCreating Benefits')
    do_print('    Creating Death')  # {{{
    capital_benefit = Benefit()
    capital_benefit.code = 'death_capital'
    capital_benefit.name = 'Capital Décès'
    capital_benefit.start_date = _base_date
    capital_benefit.insurer = insurer
    capital_benefit.beneficiary_kind = 'manual_list'
    capital_benefit.company = company
    capital_benefit.indemnification_kind = 'capital'
    capital_benefit.loss_descs.append(LossDesc(death.id))
    capital_benefit.automatically_deliver = True
    capital_benefit.eligibility_rules.new()
    capital_benefit.eligibility_rules[0].rule = capital_eligibility_rule
    capital_benefit.refuse_from_rules = True
    capital_benefit.eligibility_decisions.append(
        BenefitEligibilityDecision(automatically_accepted.id))
    capital_benefit.eligibility_decisions.append(
        BenefitEligibilityDecision(automatically_refused.id))
    capital_benefit.refuse_decision_default = automatically_refused
    capital_benefit.accept_decision_default = automatically_accepted
    capital_benefit.products.append(AccountProduct(claim_product.id))
    capital_benefit.benefit_rules.new()
    rule = capital_benefit.benefit_rules[0]
    rule.indemnification_rule = benefit_capital_rule
    capital_benefit.save()
    # }}}

    do_print('    Creating Group Incapacity')  # {{{
    group_incapacity_benefit = Benefit()
    group_incapacity_benefit.code = 'group_incapacity'
    group_incapacity_benefit.name = 'Incapacité de travail'
    group_incapacity_benefit.is_group = True
    group_incapacity_benefit.start_date = _base_date
    group_incapacity_benefit.insurer = insurer
    group_incapacity_benefit.beneficiary_kind = 'subscriber_then_covered'
    group_incapacity_benefit.company = company
    group_incapacity_benefit.indemnification_kind = 'period'
    group_incapacity_benefit.loss_descs.append(LossDesc(work_interruption.id))
    group_incapacity_benefit.automatically_deliver = True
    group_incapacity_benefit.extra_data_def.append(get_extra_data(
            'date_d_effet_d_indemnisation'))
    group_incapacity_benefit.eligibility_rules.new()
    group_incapacity_benefit.eligibility_rules[0].rule = \
        benefit_eligibility_rule
    group_incapacity_benefit.refuse_from_rules = True
    group_incapacity_benefit.eligibility_decisions.append(
        BenefitEligibilityDecision(automatically_accepted.id))
    group_incapacity_benefit.eligibility_decisions.append(
        BenefitEligibilityDecision(automatically_refused.id))
    group_incapacity_benefit.refuse_decision_default = automatically_refused
    group_incapacity_benefit.accept_decision_default = automatically_accepted
    group_incapacity_benefit.products.append(
        AccountProduct(claim_product_taxed.id))
    group_incapacity_benefit.products.append(
        AccountProduct(claim_product_reduced_taxed.id))
    group_incapacity_benefit.company_products.append(
        AccountProduct(claim_product.id))

    group_incapacity_benefit.benefit_rules.new()
    rule = group_incapacity_benefit.benefit_rules[0]
    rule.indemnification_rules.append(
        get_rule('coog_traitement_journalier_par_tranche_de_salaire'))
    rule.deductible_rules.append(
        get_rule('coog_franchise_fixe_toute_nature_d_arret_confondue'))
    rule.deductible_rules.append(
        get_rule('coog_franchise_fixe_toute_nature_d_arret_confondue'
            '_pour_un_arret_total'))
    rule.deductible_rules.append(
        get_rule('coog_franchise_relais_conventation'))
    rule.revaluation_rules.append(
        get_rule('coog_regle_standard_de_calcul_de_la_revalorisation'))
    group_incapacity_benefit.save()
    # }}}

    do_print('\nCreating Item descs')
    do_print('    Creating House Item Desc')  # {{{
    house_item_desc = ItemDesc()
    house_item_desc.name = 'Habitation'
    house_item_desc.code = 'house_generic_item_desc'
    house_item_desc.kind = None
    house_item_desc.extra_data_def.append(ExtraData(house_type.id))
    house_item_desc.extra_data_def.append(ExtraData(house_size.id))
    house_item_desc.extra_data_def.append(ExtraData(house_rooms.id))
    house_item_desc.extra_data_def.append(
        ExtraData(house_construction_date.id))
    house_item_desc.extra_data_def.append(ExtraData(house_floor.id))
    house_item_desc.save()
    # }}}

    do_print('    Creating Life Person Item Desc')  # {{{
    life_person_item_desc = ItemDesc()
    life_person_item_desc.name = 'Personne'
    life_person_item_desc.code = 'life_person_item_desc'
    life_person_item_desc.kind = 'person'
    life_person_item_desc.extra_data_def.append(ExtraData(job_category.id))
    life_person_item_desc.save()
    # }}}

    do_print('    Creating Loan Person Item Desc')  # {{{
    loan_person_item_desc = ItemDesc()
    loan_person_item_desc.name = 'Emprunteur'
    loan_person_item_desc.code = 'loan_person_item_desc'
    loan_person_item_desc.kind = 'person'
    loan_person_item_desc.extra_data_def.append(ExtraData(job_category.id))
    loan_person_item_desc.extra_data_def.append(
        ExtraData(co_borrower_relation.id))
    loan_person_item_desc.save()
    # }}}

    do_print('    Creating Funeral Item Desc')  # {{{
    funeral_item_desc = ItemDesc()
    funeral_item_desc.name = 'Personne'
    funeral_item_desc.code = 'funeral_item_desc'
    funeral_item_desc.kind = 'person'
    funeral_item_desc.save()
    # }}}

    do_print('    Creating Employee Item Desc')  # {{{
    employee_item_desc = ItemDesc()
    employee_item_desc.name = 'Employé'
    employee_item_desc.code = 'employee_item_desc'
    employee_item_desc.kind = 'person'
    employee_item_desc.extra_data_def.append(ExtraData(job_start.id))
    employee_item_desc.extra_data_def.append(ExtraData(job_end.id))
    employee_item_desc.covered_element_end_reasons.append(
        CoveredEndReason(left_reason.id))
    employee_item_desc.covered_element_end_reasons.append(
        CoveredEndReason(fired_reason.id))
    employee_item_desc.save()
    # }}}

    do_print('    Creating Subsidiary Item Desc')  # {{{
    subsidiary_item_desc = ItemDesc()
    subsidiary_item_desc.name = 'Filiale'
    subsidiary_item_desc.code = 'subsidiary_item_desc'
    subsidiary_item_desc.kind = 'subsidiary'
    subsidiary_item_desc.sub_item_descs.append(ItemDesc(employee_item_desc.id))
    subsidiary_item_desc.covered_element_end_reasons.append(
        CoveredEndReason(sell_reason.id))
    subsidiary_item_desc.save()
    # }}}

    do_print('    Creating Employee Category Item Desc')  # {{{
    category_item_desc = ItemDesc()
    category_item_desc.name = 'Catégorie'
    category_item_desc.code = 'category_item_desc'
    category_item_desc.kind = None
    category_item_desc.extra_data_def.append(ExtraData(employee_type.id))
    category_item_desc.sub_item_descs.append(ItemDesc(subsidiary_item_desc.id))
    category_item_desc.save()
    # }}}

    do_print('\nCreating Coverages')
    do_print('    Creating Personal Responsability Coverage')  # {{{
    responsability_coverage = Coverage()
    responsability_coverage.company = company
    responsability_coverage.currency = currency
    responsability_coverage.name = 'Responsabilité civile'
    responsability_coverage.code = 'responsability_coverage'
    responsability_coverage.start_date = _base_date
    responsability_coverage.account_for_billing = \
        responsability_coverage_account
    responsability_coverage.insurer = insurer
    responsability_coverage.family = 'generic'
    responsability_coverage.sequence = 10
    responsability_coverage.item_desc = house_item_desc
    responsability_coverage.subscription_behaviour = 'mandatory'
    responsability_coverage.premium_rules.new()
    responsability_coverage.premium_rules[0].rule = responsability_rating_rule
    responsability_coverage.premium_rules[0].match_contract_frequency = True
    responsability_coverage.premium_rules[0].frequency = 'yearly_365'
    responsability_coverage.save()
    # }}}

    do_print('    Creating Fire Coverage')  # {{{
    fire_coverage = Coverage()
    fire_coverage.company = company
    fire_coverage.currency = currency
    fire_coverage.name = 'Incendie'
    fire_coverage.code = 'fire_coverage'
    fire_coverage.start_date = _base_date
    fire_coverage.account_for_billing = fire_coverage_account
    fire_coverage.insurer = insurer
    fire_coverage.family = 'generic'
    fire_coverage.sequence = 20
    fire_coverage.item_desc = house_item_desc
    fire_coverage.extra_data_def.append(fire_damage_limit)
    fire_coverage.extra_data_def.append(electrical_fires)
    fire_coverage.subscription_behaviour = 'defaulted'
    fire_coverage.premium_rules.new()
    fire_coverage.premium_rules[0].rule = fire_rating_rule
    fire_coverage.premium_rules[0].match_contract_frequency = True
    fire_coverage.premium_rules[0].frequency = 'yearly_365'
    fire_coverage.save()
    # }}}

    do_print('    Creating Death Coverage')  # {{{
    death_coverage = Coverage()
    death_coverage.company = company
    death_coverage.currency = currency
    death_coverage.name = 'Décès'
    death_coverage.code = 'death_coverage'
    death_coverage.start_date = _base_date
    death_coverage.account_for_billing = death_coverage_account
    death_coverage.insurer = insurer
    death_coverage.family = 'life'
    death_coverage.insurance_kind = 'death'
    death_coverage.sequence = 10
    death_coverage.item_desc = life_person_item_desc
    death_coverage.subscription_behaviour = 'mandatory'
    death_coverage.extra_data_def.append(double_for_accidents)
    death_coverage.premium_rules.new()
    death_coverage.premium_rules[0].rule = death_rating_rule
    death_coverage.premium_rules[0].match_contract_frequency = True
    death_coverage.premium_rules[0].frequency = 'yearly_365'
    death_coverage.coverage_amount_rules.new()
    death_coverage.coverage_amount_rules[0].rule = coverage_amount_rule
    death_coverage.coverage_amount_rules[0].rule_extra_data = {
        'minimum_amount': 10000,
        'maximum_amount': 100000,
        'amount_step': 10000,
        }
    death_coverage.coverage_amount_rules[0].free_input = False
    death_coverage.eligibility_rules.new()
    death_coverage.eligibility_rules[0].rule = option_age_eligibility_rule
    death_coverage.eligibility_rules[0].rule_extra_data = {
        'age_kind': 'real',
        'max_age_for_option': 76,
        }
    death_coverage.underwriting_rules.new()
    death_coverage.underwriting_rules[-1].rule = underwriting_rule
    death_coverage.underwriting_rules[-1].decisions.append(
        UnderwritingDecision(option_accepted.id))
    death_coverage.underwriting_rules[-1].decisions.append(
        UnderwritingDecision(option_accepted_conditions.id))
    death_coverage.underwriting_rules[-1].decisions.append(
        UnderwritingDecision(option_pending.id))
    death_coverage.underwriting_rules[-1].decisions.append(
        UnderwritingDecision(option_denied.id))
    death_coverage.underwriting_rules[-1].accepted_decision = option_accepted
    death_coverage.beneficiaries_clauses.append(
        Clause(standard_beneficiary_clause.id))
    death_coverage.beneficiaries_clauses.append(
        Clause(custom_beneficiary_clause.id))
    death_coverage.default_beneficiary_clause = standard_beneficiary_clause
    death_coverage.benefits.append(Benefit(capital_benefit.id))
    death_coverage.save()
    # }}}

    do_print('    Creating Loan Death Coverage')  # {{{
    loan_death_coverage = Coverage()
    loan_death_coverage.company = company
    loan_death_coverage.currency = currency
    loan_death_coverage.name = 'Décès'
    loan_death_coverage.code = 'loan_death_coverage'
    loan_death_coverage.start_date = _base_date
    loan_death_coverage.account_for_billing = death_loan_coverage_account
    loan_death_coverage.insurer = insurer
    loan_death_coverage.family = 'loan'
    loan_death_coverage.insurance_kind = 'death'
    loan_death_coverage.sequence = 10
    loan_death_coverage.item_desc = loan_person_item_desc
    loan_death_coverage.subscription_behaviour = 'mandatory'
    loan_death_coverage.premium_rules.new()
    loan_death_coverage.premium_rules[0].rule = loan_death_rating_rule
    loan_death_coverage.premium_rules[0].match_contract_frequency = True
    loan_death_coverage.premium_rules[0].frequency = 'yearly_365'
    loan_death_coverage.eligibility_rules.new()
    loan_death_coverage.eligibility_rules[0].rule = option_age_eligibility_rule
    loan_death_coverage.eligibility_rules[0].rule_extra_data = {
        'age_kind': 'real',
        'max_age_for_option': 80,
        }
    loan_death_coverage.beneficiaries_clauses.append(
        Clause(loan_beneficiary_clause.id))
    loan_death_coverage.beneficiaries_clauses.append(
        Clause(custom_beneficiary_clause.id))
    loan_death_coverage.default_beneficiary_clause = loan_beneficiary_clause
    loan_death_coverage.save()
    # }}}

    do_print('    Creating Unemployment Coverage')  # {{{
    unemployment_coverage = Coverage()
    unemployment_coverage.company = company
    unemployment_coverage.currency = currency
    unemployment_coverage.name = 'Interruption Temporaire de Travail'
    unemployment_coverage.code = 'unemployment_coverage'
    unemployment_coverage.start_date = _base_date
    unemployment_coverage.account_for_billing = unemployment_coverage_account
    unemployment_coverage.insurer = insurer
    unemployment_coverage.family = 'life'
    unemployment_coverage.insurance_kind = 'temporary_disability'
    unemployment_coverage.sequence = 20
    unemployment_coverage.item_desc = life_person_item_desc
    unemployment_coverage.subscription_behaviour = 'defaulted'
    unemployment_coverage.extra_data_def.append(
        ExtraData(deductible_duration.id))
    unemployment_coverage.extra_data_def.append(
        ExtraData(per_day_amount.id))
    unemployment_coverage.premium_rules.new()
    unemployment_coverage.premium_rules[0].rule = unemployment_rating_rule
    unemployment_coverage.premium_rules[0].match_contract_frequency = True
    unemployment_coverage.premium_rules[0].frequency = 'yearly_365'
    unemployment_coverage.save()
    # }}}

    do_print('    Creating Loan unemployment Coverage')  # {{{
    loan_unemployment_coverage = Coverage()
    loan_unemployment_coverage.company = company
    loan_unemployment_coverage.currency = currency
    loan_unemployment_coverage.name = 'Interruption Temporaire de Travail'
    loan_unemployment_coverage.code = 'loan_unemployment_coverage'
    loan_unemployment_coverage.start_date = _base_date
    loan_unemployment_coverage.account_for_billing = \
        unemployment_loan_coverage_account
    loan_unemployment_coverage.insurer = insurer
    loan_unemployment_coverage.family = 'loan'
    loan_unemployment_coverage.insurance_kind = 'temporary_disability'
    loan_unemployment_coverage.sequence = 20
    loan_unemployment_coverage.item_desc = loan_person_item_desc
    loan_unemployment_coverage.subscription_behaviour = 'defaulted'
    loan_unemployment_coverage.extra_data_def.append(
        ExtraData(deductible_duration.id))
    loan_unemployment_coverage.premium_rules.new()
    loan_unemployment_coverage.premium_rules[0].rule = \
        loan_unemployment_rating_rule
    loan_unemployment_coverage.premium_rules[0].match_contract_frequency = True
    loan_unemployment_coverage.premium_rules[0].frequency = 'yearly_365'
    loan_unemployment_coverage.save()
    # }}}

    do_print('    Creating Disability Coverage')  # {{{
    disability_coverage = Coverage()
    disability_coverage.company = company
    disability_coverage.currency = currency
    disability_coverage.name = 'Invalidité'
    disability_coverage.code = 'disability_coverage'
    disability_coverage.start_date = _base_date
    disability_coverage.account_for_billing = disability_coverage_account
    disability_coverage.insurer = insurer
    disability_coverage.family = 'life'
    disability_coverage.insurance_kind = 'partial_disability'
    disability_coverage.sequence = 30
    disability_coverage.item_desc = life_person_item_desc
    disability_coverage.subscription_behaviour = 'optional'
    disability_coverage.extra_data_def.append(ExtraData(monthly_annuity.id))
    disability_coverage.premium_rules.new()
    disability_coverage.premium_rules[0].rule = disability_rating_rule
    disability_coverage.premium_rules[0].match_contract_frequency = True
    disability_coverage.premium_rules[0].frequency = 'yearly_365'
    disability_coverage.save()
    # }}}

    do_print('    Creating Loan Disability Coverage')  # {{{
    loan_disability_coverage = Coverage()
    loan_disability_coverage.company = company
    loan_disability_coverage.currency = currency
    loan_disability_coverage.name = 'Invalidité'
    loan_disability_coverage.code = 'loan_disability_coverage'
    loan_disability_coverage.start_date = _base_date
    loan_disability_coverage.account_for_billing = \
        disability_loan_coverage_account
    loan_disability_coverage.insurer = insurer
    loan_disability_coverage.family = 'loan'
    loan_disability_coverage.insurance_kind = 'partial_disability'
    loan_disability_coverage.sequence = 30
    loan_disability_coverage.item_desc = loan_person_item_desc
    loan_disability_coverage.subscription_behaviour = 'optional'
    loan_disability_coverage.premium_rules.new()
    loan_disability_coverage.premium_rules[0].rule = \
        loan_disability_rating_rule
    loan_disability_coverage.premium_rules[0].match_contract_frequency = True
    loan_disability_coverage.premium_rules[0].frequency = 'yearly_365'
    loan_disability_coverage.save()
    # }}}

    do_print('    Creating Funeral Coverage')  # {{{
    funeral_coverage = Coverage()
    funeral_coverage.company = company
    funeral_coverage.currency = currency
    funeral_coverage.name = 'Obsèques'
    funeral_coverage.code = 'funeral_coverage'
    funeral_coverage.start_date = _base_date
    funeral_coverage.account_for_billing = funeral_coverage_account
    funeral_coverage.insurer = insurer
    funeral_coverage.family = 'life'
    funeral_coverage.sequence = 10
    funeral_coverage.item_desc = funeral_item_desc
    funeral_coverage.subscription_behaviour = 'mandatory'
    funeral_coverage.coverage_amount_rules.new()
    funeral_coverage.coverage_amount_rules[0].rule = coverage_amount_rule
    funeral_coverage.coverage_amount_rules[0].rule_extra_data = {
        'minimum_amount': 1500,
        'maximum_amount': 6000,
        'amount_step': 1500,
        }
    funeral_coverage.premium_rules.new()
    funeral_coverage.premium_rules[0].rule = funeral_rating_rule
    funeral_coverage.premium_rules[0].match_contract_frequency = True
    funeral_coverage.premium_rules[0].frequency = 'yearly_365'
    funeral_coverage.reduction_rules.new()
    funeral_coverage.reduction_rules[0].rule = funeral_reduction_rule
    funeral_coverage.reduction_rules[0].eligibility_rule = \
        funeral_reduction_eligibility_rule
    funeral_coverage.reduction_rules[0].eligibility_rule_extra_data = {
        'nombre_annees': 1,
        'verification_paiement': True,
        }
    funeral_coverage.surrender_rules.new()
    funeral_coverage.surrender_rules[0].rule = funeral_surrender_rule
    funeral_coverage.surrender_rules[0].surrender_account = \
        funeral_surrender_account
    funeral_coverage.surrender_rules[0].eligibility_rule = \
        funeral_surrender_eligibility_rule
    funeral_coverage.surrender_rules[0].eligibility_rule_extra_data = {
        'nombre_annees': 2,
        'verification_paiement': False,
        }
    funeral_coverage.beneficiaries_clauses.append(
        Clause(funeral_beneficiary_clause.id))
    funeral_coverage.beneficiaries_clauses.append(
        Clause(custom_beneficiary_clause.id))
    funeral_coverage.default_beneficiary_clause = funeral_beneficiary_clause
    funeral_coverage.extra_details_rule.new()
    funeral_coverage.extra_details_rule[0].rule = funeral_details_rule
    funeral_coverage.save()
    # }}}

    do_print('    Creating Group Incapacity Coverage')  # {{{
    group_incapacity_coverage = Coverage()
    group_incapacity_coverage.company = company
    group_incapacity_coverage.currency = currency

    group_incapacity_coverage.name = 'Incapacité'
    group_incapacity_coverage.code = 'group_incapacity_coverage'
    group_incapacity_coverage.is_group = True
    group_incapacity_coverage.start_date = _base_date
    group_incapacity_coverage.account_for_billing = \
        group_incapacity_coverage_account
    group_incapacity_coverage.insurer = insurer
    group_incapacity_coverage.family = 'life'
    group_incapacity_coverage.sequence = 10
    group_incapacity_coverage.item_desc = category_item_desc
    group_incapacity_coverage.subscription_behaviour = 'mandatory'
    group_incapacity_coverage.benefits.append(
        Benefit(group_incapacity_benefit.id))
    group_incapacity_coverage.extra_data_def.append(
        ExtraData(relapse_threshold.id))
    group_incapacity_coverage.save()
    # }}}

    do_print('\nCreating products')
    do_print('    Creating House Insurance Product')  # {{{
    house_product = Product()
    house_product.name = 'Assurance habitation'
    house_product.code = 'house_product'
    house_product.start_date = _base_date
    house_product.company = company
    house_product.currency = currency
    house_product.quote_number_sequence = quote_sequence
    house_product.contract_generator = contract_sequence
    house_product.coverages.append(responsability_coverage)
    house_product.coverages.append(fire_coverage)
    house_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'monthly_sepa')])[0])
    house_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'quarterly_sepa')])[0])
    house_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'half_yearly_sepa')])[0])
    house_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_sepa')])[0])
    house_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_manual')])[0])
    house_product.term_renewal_rule.new()
    house_product.term_renewal_rule[0].rule = product_term_renewal_rule
    house_product.term_renewal_rule[0].allow_renewal = True
    house_product.com_products.new()
    house_product.com_products[0].name = 'Habitation +'
    house_product.com_products[0].code = 'habitation_plus'
    house_product.com_products[0].start_date = _base_date
    house_product.com_products[0].dist_networks.append(
        DistributionNetwork.find([('code', '=', 'C1')])[0])
    house_product.document_rules.new()
    house_product.document_rules[0].documents.new()
    house_product.document_rules[0].documents[0].document = subscription_request
    house_product.document_rules[0].documents[0].blocking = True
    house_product.save()

    generic_process.for_products.append(house_product)
    generic_process.save()
    # }}}

    do_print('    Creating life product')  # {{{
    life_product = Product()
    life_product.name = 'Assurance Prévoyance'
    life_product.code = 'life_product'
    life_product.start_date = _base_date
    life_product.company = company
    life_product.currency = currency
    life_product.quote_number_sequence = quote_sequence
    life_product.contract_generator = contract_sequence
    life_product.coverages.append(Coverage(death_coverage.id))
    life_product.coverages.append(Coverage(unemployment_coverage.id))
    life_product.coverages.append(Coverage(disability_coverage.id))
    life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'monthly_sepa')])[0])
    life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'quarterly_sepa')])[0])
    life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'half_yearly_manual')])[0])
    life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_manual')])[0])
    life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_sepa')])[0])
    life_product.term_renewal_rule.new()
    life_product.term_renewal_rule[0].rule = product_term_renewal_rule
    life_product.term_renewal_rule[0].allow_renewal = True
    life_product.com_products.new()
    life_product.com_products[0].name = 'Prévoyance +'
    life_product.com_products[0].code = 'prevoyance_plus'
    life_product.com_products[0].start_date = _base_date
    life_product.com_products[0].dist_networks.append(
        DistributionNetwork.find([('code', '=', 'C1')])[0])
    life_product.com_products[0].dist_authorized_channels.append(
        Channel.find([])[0])
    life_product.document_rules.new()
    life_product.document_rules[0].documents.new()
    life_product.document_rules[0].documents[0].document = subscription_request
    life_product.document_rules[0].documents[0].blocking = True
    life_product.extra_data_def.append(ExtraData(analyse_forcee.id))
    life_product.save()

    life_process.for_products.append(life_product)
    life_process.save()
    # }}}

    do_print('    Creating loan product')  # {{{
    loan_product = Product()
    loan_product.name = 'Assurance Emprunteur'
    loan_product.code = 'loan_product'
    loan_product.start_date = _base_date
    loan_product.company = company
    loan_product.currency = currency
    loan_product.quote_number_sequence = quote_sequence
    loan_product.contract_generator = contract_sequence
    loan_product.coverages.append(Coverage(loan_death_coverage.id))
    loan_product.coverages.append(Coverage(loan_unemployment_coverage.id))
    loan_product.coverages.append(Coverage(loan_disability_coverage.id))
    loan_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'monthly_sepa')])[0])
    loan_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'quarterly_sepa')])[0])
    loan_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'half_yearly_manual')])[0])
    loan_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_manual')])[0])
    loan_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_sepa')])[0])
    loan_product.average_loan_premium_rule = loan_premium_rule
    loan_product.com_products.new()
    loan_product.com_products[0].name = 'Emprunteur +'
    loan_product.com_products[0].code = 'emprunteur_plus'
    loan_product.com_products[0].start_date = _base_date
    loan_product.com_products[0].dist_networks.append(
        DistributionNetwork.find([('code', '=', 'C1')])[0])
    loan_product.extra_data_def.append(ExtraData(reduction_libre.id))
    loan_product.extra_data = {'libelle_editique': 'Prêt / voyez tout'}
    loan_product.document_rules.new()
    loan_product.document_rules[0].documents.new()
    loan_product.document_rules[0].documents[0].document = subscription_request
    loan_product.document_rules[0].documents[0].blocking = True
    loan_product.document_rules[0].documents.new()
    loan_product.document_rules[0].documents[1].document = loan_planning
    loan_product.document_rules[0].documents[1].blocking = True
    loan_product.save()

    loan_process.for_products.append(loan_product)
    loan_process.save()
    # }}}

    do_print('    Creating funeral product')  # {{{
    funeral_product = Product()
    funeral_product.name = 'Assurance Obsèques'
    funeral_product.code = 'funeral_product'
    funeral_product.start_date = _base_date
    funeral_product.company = company
    funeral_product.currency = currency
    funeral_product.quote_number_sequence = quote_sequence
    funeral_product.contract_generator = contract_sequence
    funeral_product.coverages.append(Coverage(funeral_coverage.id))
    funeral_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'monthly_sepa')])[0])
    funeral_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'quarterly_sepa')])[0])
    funeral_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'half_yearly_manual')])[0])
    funeral_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_manual')])[0])
    funeral_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_sepa')])[0])
    funeral_product.com_products.new()
    funeral_product.com_products[0].name = 'Obsèques +'
    funeral_product.com_products[0].code = 'obseques_plus'
    funeral_product.com_products[0].start_date = _base_date
    funeral_product.com_products[0].dist_networks.append(
        DistributionNetwork.find([('code', '=', 'C1')])[0])
    funeral_product.document_rules.new()
    funeral_product.document_rules[0].documents.new()
    funeral_product.document_rules[0].documents[0].document = \
        subscription_request
    funeral_product.document_rules[0].documents[0].blocking = True
    funeral_product.save()

    life_process.for_products.append(funeral_product)
    life_process.save()
    # }}}

    do_print('    Creating group life product')  # {{{
    group_life_product = Product()
    group_life_product.name = 'Assurance Prévoyance Collective'
    group_life_product.code = 'group_life_product'
    group_life_product.start_date = _base_date
    group_life_product.company = company
    group_life_product.currency = currency
    group_life_product.is_group = True
    group_life_product.quote_number_sequence = quote_sequence
    group_life_product.contract_generator = contract_sequence
    group_life_product.coverages.append(
        Coverage(group_incapacity_coverage.id))
    group_life_product.billing_rules[-1].billing_modes.append(BillingMode.find(
            [('code', '=', 'yearly_manual')])[0])
    group_life_product.com_products.new()
    group_life_product.com_products[0].name = 'Prevoyance Co +'
    group_life_product.com_products[0].code = 'prevoyance_co_plus'
    group_life_product.com_products[0].start_date = _base_date
    group_life_product.com_products[0].dist_networks.append(
        DistributionNetwork.find([('code', '=', 'C1')])[0])
    group_life_product.default_termination_claim_behaviour = \
        'stop_indemnifications'
    group_life_product.save()
    # }}}

    do_print('\nCreating Questionnaire')
    do_print('    Creating Questions')  # {{{
    refund_overpayment_question = ExtraData()
    refund_overpayment_question.type_ = 'selection'
    refund_overpayment_question.kind = 'questionnaire'
    refund_overpayment_question.string = 'Souhaitez vous bénéficiez de '
    refund_overpayment_question.string += 'remboursement pour les dépassement '
    refund_overpayment_question.string += 'd\'honoraires ?'
    refund_overpayment_question.name = 'refund_question'
    refund_overpayment_question.selection = '''oui:Oui\nnon:Non'''
    refund_overpayment_question.selection_sorted = True
    refund_overpayment_question.has_default_value = False
    refund_overpayment_question.sequence_order = 49
    refund_overpayment_question.save()

    eyes_and_tooth_question = ExtraData()
    eyes_and_tooth_question.type_ = 'selection'
    eyes_and_tooth_question.kind = 'questionnaire'
    eyes_and_tooth_question.string = \
        'Souhaitez vous renforcer l\'Optique et/ou le Dentaire?'
    eyes_and_tooth_question.name = 'eyes_and_tooth_question'
    eyes_and_tooth_question.selection = '''oui:Oui\nnon:Non'''
    eyes_and_tooth_question.selection_sorted = True
    eyes_and_tooth_question.has_default_value = False
    eyes_and_tooth_question.sequence_order = 48
    eyes_and_tooth_question.save()

    simple_coverage_question = ExtraData()
    simple_coverage_question.type_ = 'selection'
    simple_coverage_question.kind = 'questionnaire'
    simple_coverage_question.string = \
        'Souhaitez vous être couvert pour l\'essentiel ?'
    simple_coverage_question.name = 'simple_coverage_question'
    simple_coverage_question.selection = '''oui:Oui\nnon:Non'''
    simple_coverage_question.selection_sorted = True
    simple_coverage_question.has_default_value = False
    simple_coverage_question.sequence_order = 47
    simple_coverage_question.save()

    heavy_coverage_question = ExtraData()
    heavy_coverage_question.type_ = 'selection'
    heavy_coverage_question.kind = 'questionnaire'
    heavy_coverage_question.string = 'Selon vous, est-ce important de se '
    heavy_coverage_question.string += 'prémunir (vous et vos proches) contre '
    heavy_coverage_question.string += 'les risques lourds de la vie '
    heavy_coverage_question.string += '(incapacité, décès) ?'
    heavy_coverage_question.name = 'heavy_coverage_question'
    heavy_coverage_question.selection = '''oui:Oui\nnon:Non'''
    heavy_coverage_question.selection_sorted = True
    heavy_coverage_question.has_default_value = False
    heavy_coverage_question.sequence_order = 50
    heavy_coverage_question.save()

    maximal_coverage_question = ExtraData()
    maximal_coverage_question.type_ = 'selection'
    maximal_coverage_question.kind = 'questionnaire'
    maximal_coverage_question.string = \
        'Souhaitez-vous bénéficier de la couverture maximale ?'
    maximal_coverage_question.name = 'maximal_coverage_question'
    maximal_coverage_question.selection = '''oui:Oui\nnon:Non'''
    maximal_coverage_question.selection_sorted = True
    maximal_coverage_question.has_default_value = False
    maximal_coverage_question.sequence_order = 51
    maximal_coverage_question.save()
    # }}}

    do_print('    Creating Rules')  # {{{
    questionnaire_sante_rule = RuleEngine()
    questionnaire_sante_rule.algorithm = '''
return [{
        'score': 100,
        'description': 'La solution qui vous convient',
        'eligible': True,
        'product': 'life_product',
        }]
    '''
    questionnaire_sante_rule.context = rule_context
    questionnaire_sante_rule.name = 'Rule Santé MDP'
    questionnaire_sante_rule.status = 'validated'
    questionnaire_sante_rule.type_ = 'questionnaire'
    questionnaire_sante_rule.save()

    questionnaire_health_rule = RuleEngine()
    questionnaire_health_rule.algorithm = '''
return [{
        'score': 50,
        'description': 'La formule qui vous convient',
        'eligible': False,
        'product': 'life_product',
        }]
    '''
    questionnaire_health_rule.context = rule_context
    questionnaire_health_rule.name = 'Rule Prévoyancd MDP'
    questionnaire_health_rule.status = 'validated'
    questionnaire_health_rule.type_ = 'questionnaire'
    questionnaire_health_rule.save()
    # }}}

    do_print('    Creating health and life Questionnaire')  # {{{
    questionnaire_sante_prev = Questionnaire()
    questionnaire_sante_prev.code = 'sante_et_prevoyance_mpd'
    questionnaire_sante_prev.company = company
    questionnaire_sante_prev.description = \
        'Description pour Santé et Prévoyance'
    questionnaire_sante_prev.icon = IrUiIcon(10)
    questionnaire_sante_prev.name = 'Santé et Prévoyance'
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(refund_overpayment_question.id))
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(eyes_and_tooth_question.id))
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(simple_coverage_question.id))
    questionnaire_sante_prev.parts[0].mandatory = True
    questionnaire_sante_prev.parts[0].name = 'Santé MPD'
    questionnaire_sante_prev.parts[0].mandatory = True
    questionnaire_sante_prev.parts[0].rule = questionnaire_sante_rule
    questionnaire_sante_prev.parts[0].sequence = 1

    questionnaire_sante_prev.parts.new()
    questionnaire_sante_prev.parts[1].extra_data_def.append(
        ExtraData(heavy_coverage_question.id))
    questionnaire_sante_prev.parts[1].extra_data_def.append(
        ExtraData(maximal_coverage_question.id))
    questionnaire_sante_prev.parts[1].mandatory = False
    questionnaire_sante_prev.parts[1].name = 'Prévoyance MPD'
    questionnaire_sante_prev.parts[1].mandatory = True
    questionnaire_sante_prev.parts[1].rule = questionnaire_health_rule
    questionnaire_sante_prev.parts[1].sequence = 2

    questionnaire_sante_prev.products.append(Product(life_product.id))
    questionnaire_sante_prev.sequence = 124
    questionnaire_sante_prev.save()
    # }}}

    do_print('    Creating health Questionnaire')  # {{{
    questionnaire_sante_prev = Questionnaire()
    questionnaire_sante_prev.code = 'sante_mpd'
    questionnaire_sante_prev.company = company
    questionnaire_sante_prev.description = 'Description pour Santé'
    questionnaire_sante_prev.icon = IrUiIcon(10)
    questionnaire_sante_prev.name = 'Santé'
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(refund_overpayment_question.id))
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(eyes_and_tooth_question.id))
    questionnaire_sante_prev.parts[0].extra_data_def.append(
        ExtraData(simple_coverage_question.id))
    questionnaire_sante_prev.parts[0].mandatory = True
    questionnaire_sante_prev.parts[0].name = 'Santé MPD'
    questionnaire_sante_prev.parts[0].mandatory = True
    questionnaire_sante_prev.parts[0].rule = questionnaire_sante_rule
    questionnaire_sante_prev.parts[0].sequence = 1

    questionnaire_sante_prev.products.append(Product(life_product.id))
    questionnaire_sante_prev.sequence = 124
    questionnaire_sante_prev.save()
    # }}}
# }}}

if CREATE_COMMISSION_CONFIG:  # {{{
    do_print('\nCreating commission configuration')
    do_print('    Loading configuration')  # {{{
    broker, = Party.find([('name', '=', _broker_name)])
    # }}}

    do_print('    Creating commission plans extra data')  # {{{
    vip_agent = ExtraData()
    vip_agent.type_ = 'boolean'
    vip_agent.kind = 'agent'
    vip_agent.string = 'Protocole VIP'
    vip_agent.name = 'vip_agent'
    vip_agent.save()
    # }}}

    do_print('    Creating commission plans rules')  # {{{
    broker_share_rule = RuleEngine()
    broker_share_rule.context = commission_context
    broker_share_rule.name = 'Commission Courtier'
    broker_share_rule.short_name = 'commissionnement_courtier'
    broker_share_rule.status = 'validated'
    broker_share_rule.type_ = 'commission'
    broker_share_rule.extra_data_used.append(ExtraData(vip_agent.id))
    broker_share_rule.algorithm = '''
return montant_ligne_quittance() * (0.15 if compl_vip_agent() else 0.11)
'''
    broker_share_rule.save()

    broker_flat_rule = RuleEngine()
    broker_flat_rule.context = commission_context
    broker_flat_rule.name = 'Commission Courtier Constant'
    broker_flat_rule.short_name = 'commissionnement_courtier_constant'
    broker_flat_rule.status = 'validated'
    broker_flat_rule.type_ = 'commission'
    broker_flat_rule.extra_data_used.append(ExtraData(vip_agent.id))
    broker_flat_rule.algorithm = '''
return 1.0 if compl_vip_agent() else 0.75
'''
    broker_flat_rule.save()
    # }}}

    do_print('    Creating insurer commission plans')  # {{{
    insurer_plan = CommissionPlan()
    insurer_plan.name = 'Commissionnement Assureur'
    insurer_plan.code = 'commissionnement_assureur'
    insurer_plan.commission_method = 'payment'
    insurer_plan.commission_product = insurer_account_product
    insurer_plan.type_ = 'principal'
    insurer_plan.lines.new()
    insurer_plan.lines[0].formula = 'amount * 0.2'
    insurer_plan.lines[0].options.append(Coverage(responsability_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(fire_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(death_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(unemployment_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(disability_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(loan_death_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(funeral_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(group_incapacity_coverage.id))
    insurer_plan.lines[0].options.append(
        Coverage(loan_unemployment_coverage.id))
    insurer_plan.lines[0].options.append(Coverage(loan_disability_coverage.id))
    insurer_plan.save()
    # }}}

    do_print('    Creating broker commission plans')  # {{{
    broker_plan = CommissionPlan()
    broker_plan.name = 'Commissionnement Courtier'
    broker_plan.code = 'commissionnement_courtier'
    broker_plan.commission_method = 'payment'
    broker_plan.commission_product = broker_account_product
    broker_plan.type_ = 'agent'
    broker_plan.insurer_plan = insurer_plan
    broker_plan.lines.new()
    broker_plan.lines[0].use_rule_engine = True
    broker_plan.lines[0].rule = broker_share_rule
    broker_plan.lines[0].options.append(Coverage(responsability_coverage.id))
    broker_plan.lines[0].options.append(Coverage(fire_coverage.id))
    broker_plan.lines[0].options.append(Coverage(death_coverage.id))
    broker_plan.lines[0].options.append(Coverage(unemployment_coverage.id))
    broker_plan.lines[0].options.append(Coverage(disability_coverage.id))
    broker_plan.lines[0].options.append(Coverage(loan_death_coverage.id))
    broker_plan.lines[0].options.append(Coverage(funeral_coverage.id))
    broker_plan.lines[0].options.append(Coverage(group_incapacity_coverage.id))
    broker_plan.lines[0].options.append(
        Coverage(loan_unemployment_coverage.id))
    broker_plan.lines[0].options.append(Coverage(loan_disability_coverage.id))
    broker_plan.extra_data_def.append(ExtraData(vip_agent.id))
    broker_plan.save()

    broker_plan_flat = CommissionPlan()
    broker_plan_flat.name = 'Commissionnement Courtier Constant'
    broker_plan_flat.code = 'commissionnement_courtier_constant'
    broker_plan_flat.commission_method = 'payment'
    broker_plan_flat.commission_product = broker_account_product
    broker_plan_flat.type_ = 'agent'
    broker_plan_flat.insurer_plan = insurer_plan
    broker_plan_flat.lines.new()
    broker_plan_flat.lines[0].use_rule_engine = True
    broker_plan_flat.lines[0].rule = broker_flat_rule
    broker_plan_flat.lines[0].options.append(Coverage(loan_death_coverage.id))
    broker_plan_flat.lines[0].options.append(
        Coverage(loan_unemployment_coverage.id))
    broker_plan_flat.lines[0].options.append(
        Coverage(loan_disability_coverage.id))
    broker_plan_flat.extra_data_def.append(ExtraData(vip_agent.id))
    broker_plan_flat.save()
    # }}}

    do_print('    Creating insurer agents')  # {{{
    insurer_agent = CommissionAgent()
    insurer_agent.company = company
    insurer_agent.currency = currency
    insurer_agent.insurer = insurer
    insurer_agent.party = insurer.party
    insurer_agent.plan = insurer_plan
    insurer_agent.type_ = 'principal'
    insurer_agent.save()
    # }}}

    do_print('    Creating broker agents')  # {{{
    broker_agent = CommissionAgent()
    broker_agent.company = company
    broker_agent.currency = currency
    broker_agent.party = broker
    broker_agent.plan = broker_plan
    broker_agent.type_ = 'agent'
    assert 'vip_agent' in broker_agent.extra_data
    broker_agent.extra_data = {'vip_agent': True}
    broker_agent.code = 'vip'
    broker_agent.save()

    broker_flat = CommissionAgent()
    broker_flat.company = company
    broker_flat.currency = currency
    broker_flat.party = broker
    broker_flat.plan = broker_plan_flat
    broker_flat.type_ = 'agent'
    broker_flat.extra_data = {'vip_agent': True}
    broker_flat.save()
    # }}}

    do_print('    Creating broker user')  # {{{
    contract_user, = User.find([('login', '=', 'contract_user')])
    broker_user = User(User.copy([contract_user.id], {})[0])
    broker_user.login = 'jean.petit'
    broker_user.password = 'azertyuiop'
    broker_user.dist_network, = DistributionNetwork.find(
        [('code', '=', 'C1010102')])
    broker_user.save()
    # }}}
# }}}

if CREATE_CONTRACTS:  # {{{
    do_print('\nCreating contracts')

    do_print('    Loading configuration')  # {{{
    broker, = Party.find([('name', '=', _broker_name)])
    lender, = Party.find([('name', '=', _lender_name)])
    insurer, = Insurer.find([])

    insurer_plan, = CommissionPlan.find(
        [('code', '=', 'commissionnement_assureur')])
    broker_plan, = CommissionPlan.find(
        [('code', '=', 'commissionnement_courtier')])
    broker_plan_flat, = CommissionPlan.find(
        [('code', '=', 'commissionnement_courtier_constant')])
    insurer_agent, = CommissionAgent.find(
        [('plan', '=', insurer_plan.id), ('party', '=', insurer.party.id)])
    broker_agent, = CommissionAgent.find(
        [('plan', '=', broker_plan.id), ('party', '=', broker.id)])
    broker_agent_flat, = CommissionAgent.find(
        [('plan', '=', broker_plan_flat.id), ('party', '=', broker.id)])

    employee_category, = ItemDesc.find([('code', '=', 'category_item_desc')])

    house_product, = Product.find([('code', '=', 'house_product')])
    life_product, = Product.find([('code', '=', 'life_product')])
    loan_product, = Product.find([('code', '=', 'loan_product')])
    funeral_product, = Product.find([('code', '=', 'funeral_product')])
    group_life_product, = Product.find([('code', '=', 'group_life_product')])

    responsability_coverage, = Coverage.find(
        [('code', '=', 'responsability_coverage')])
    fire_coverage, = Coverage.find([('code', '=', 'fire_coverage')])
    death_coverage, = Coverage.find([('code', '=', 'death_coverage')])
    unemployment_coverage, = Coverage.find(
        [('code', '=', 'unemployment_coverage')])
    disability_coverage, = Coverage.find([('code', '=', 'disability_coverage')])
    funeral_coverage, = Coverage.find([('code', '=', 'funeral_coverage')])
    group_incapacity_coverage, = Coverage.find(
        [('code', '=', 'group_incapacity_coverage')])

    standard_beneficiary_clause, = Clause.find(
        [('code', '=', 'clause_beneficiaire_standard')])
    custom_beneficiary_clause, = Clause.find(
        [('code', '=', 'clause_beneficiaire_personnalisee')])
    loan_beneficiary_clause, = Clause.find(
        [('code', '=', 'clause_beneficiaire_emprunteur')])
    funeral_beneficiary_clause, = Clause.find(
        [('code', '=', 'clause_beneficiaire_obseques')])
    # }}}

    do_print('    Creating a house contract')  # {{{
    house_subscriber = Party()
    house_subscriber.name = 'DOE'
    house_subscriber.lang = lang
    house_subscriber.first_name = 'John'
    house_subscriber.birth_date = datetime.date(1986, 11, 21)
    house_subscriber.gender = 'male'
    house_subscriber.is_person = True
    house_subscriber.all_addresses[0].street = "\n\n10 rue d'Hauteville"
    house_subscriber.all_addresses[0].zip = '75004'
    house_subscriber.all_addresses[0].city = 'PARIS'
    house_subscriber.all_addresses[0].country = country
    house_subscriber.save()

    house_subscriber_account = BankAccount()
    house_subscriber_account.owners.append(Party(house_subscriber.id))
    house_subscriber_account.start_date = None
    house_subscriber_account.currency = currency
    house_subscriber_account.number = get_iban()
    house_subscriber_account.bank, = Bank.find(
        [('bic', '=', _company_bank_bic)])
    house_subscriber_account.save()

    SubscribeContract = Wizard('contract.subscribe')
    SubscribeContract.form.signature_date = _base_contract_date
    SubscribeContract.form.distributor = DistributionNetwork.find(
        [('code', '=', 'C1010101')])[0]
    SubscribeContract.form.commercial_product = house_product.com_products[0]
    SubscribeContract.execute('action')

    house_contract = Contract.find([('product.code', '=', 'house_product')])[0]
    house_contract.subscriber = house_subscriber
    assert_eq(house_contract.agent, broker_agent)
    process_next(house_contract)
    covered = house_contract.covered_elements[0]
    covered.name = 'Résidence principale'
    assert_eq(set(covered.current_extra_data.keys()),
        {'house_type', 'house_size', 'house_rooms', 'house_construction_date'})
    covered.current_extra_data = {
        'house_type': 'appartement',
        }
    assert 'house_floor' in covered.current_extra_data
    covered.current_extra_data = {
        'house_type': 'appartement',
        'house_size': 120,
        'house_rooms': 5,
        'house_floor': 4,
        'house_construction_date': 1879,
        }
    process_next(house_contract)
    fire_option = house_contract.covered_elements[0].options[1]
    fire_option.current_extra_data = {
        'fire_damage_limit': '2000',
        'electrical_fires': True,
        }
    process_next(house_contract)
    house_contract.document_request_lines[0].received = True
    house_contract.document_request_lines[0].save()
    process_next(house_contract)
    house_contract.billing_informations[0].billing_mode = BillingMode.find(
        [('code', '=', 'yearly_sepa')])[0]
    house_contract.billing_informations[0].direct_debit_account = \
        house_subscriber_account
    house_contract.billing_informations[0].direct_debit_day = 1
    process_next(house_contract)
    process_next(house_contract)
    # }}}

    do_print('    Creating a life contract')  # {{{
    life_subscriber = Party()
    life_subscriber.name = 'DOE'
    life_subscriber.lang = lang
    life_subscriber.first_name = 'Jane'
    life_subscriber.birth_date = datetime.date(1963, 10, 2)
    life_subscriber.gender = 'female'
    life_subscriber.is_person = True
    life_subscriber.all_addresses[0].street = "\n\n20 rue d'Hauteville"
    life_subscriber.all_addresses[0].zip = '75010'
    life_subscriber.all_addresses[0].city = 'PARIS'
    life_subscriber.all_addresses[0].country = country
    life_subscriber.save()

    life_subscriber_account = BankAccount()
    life_subscriber_account.owners.append(Party(life_subscriber.id))
    life_subscriber_account.start_date = None
    life_subscriber_account.currency = currency
    life_subscriber_account.number = get_iban()
    life_subscriber_account.bank, = Bank.find(
        [('bic', '=', _company_bank_bic)])
    life_subscriber_account.start_date = None
    life_subscriber_account.save()

    SubscribeContract = Wizard('contract.subscribe')
    SubscribeContract.form.signature_date = _base_contract_date
    SubscribeContract.form.distributor = DistributionNetwork.find(
        [('code', '=', 'C1010102')])[0]
    SubscribeContract.form.commercial_product = life_product.com_products[0]
    SubscribeContract.execute('action')

    life_contract = Contract.find([('product.code', '=', 'life_product')])[0]
    life_contract.subscriber = life_subscriber
    process_next(life_contract)
    life_contract.covered_elements[0].current_extra_data = {
        'job_category': 'csp3',
        }
    life_contract.covered_elements.new()
    life_contract.covered_elements[1].party = house_subscriber
    life_contract.covered_elements[1].current_extra_data = {
        'job_category': 'csp1',
        }
    process_next(life_contract)

    SubscriptionWizard = Wizard(
        'contract.wizard.option_subscription', [life_contract])
    SubscriptionWizard.form.covered_element = life_contract.covered_elements[1]
    SubscriptionWizard.form.options[2].is_selected = True
    SubscriptionWizard.execute('update_options')
    life_contract.reload()

    death_option = life_contract.covered_elements[0].options[0]
    death_option.current_coverage_amount = Decimal(60000)
    death_option.beneficiaries_clause = standard_beneficiary_clause
    death_option.current_extra_data = {
        'double_for_accidents': True,
        }
    unemployment_option = life_contract.covered_elements[0].options[1]
    unemployment_option.current_extra_data = {
        'deductible_duration': '60',
        'per_day_amount': '150',
        }
    death_option = life_contract.covered_elements[1].options[0]
    death_option.current_coverage_amount = Decimal(20000)
    death_option.beneficiaries_clause = standard_beneficiary_clause
    death_option.current_extra_data = {
        'double_for_accidents': False,
        }
    unemployment_option = life_contract.covered_elements[1].options[1]
    unemployment_option.current_extra_data = {
        'deductible_duration': '30',
        'per_day_amount': '50',
        }
    disability_option = life_contract.covered_elements[1].options[2]
    disability_option.current_extra_data = {
        'monthly_annuity': '2000',
        }
    life_contract.save()
    process_next(life_contract)
    life_contract.document_request_lines[0].received = True
    life_contract.document_request_lines[0].save()
    process_next(life_contract)

    # Underwriting should not pass here
    try:
        process_next(life_contract)
    except UserError:
        pass
    else:
        raise Exception
    process_previous(life_contract)
    life_contract.covered_elements[0].current_extra_data = {
        'job_category': 'csp2',
        }
    life_contract.covered_elements[0].save()
    process_next(life_contract)
    # Now it should
    process_next(life_contract)
    life_contract.billing_informations[0].billing_mode, = BillingMode.find(
        [('code', '=', 'yearly_sepa')])
    life_contract.billing_informations[0].direct_debit_account = \
        life_subscriber_account
    life_contract.billing_informations[0].direct_debit_day = 1
    process_next(life_contract)
    process_next(life_contract)
    assert_eq(life_contract.extra_data_values, {})
    # }}}

    do_print('    Creating a loan contract')  # {{{
    loan_subscriber = Party()
    loan_subscriber.name = 'DOE'
    loan_subscriber.lang = lang
    loan_subscriber.first_name = 'Daisy'
    loan_subscriber.birth_date = datetime.date(1981, 4, 11)
    loan_subscriber.gender = 'female'
    loan_subscriber.is_person = True
    loan_subscriber.all_addresses[0].street = "\n\n30 rue d'Hauteville"
    loan_subscriber.all_addresses[0].zip = '75010'
    loan_subscriber.all_addresses[0].city = 'PARIS'
    loan_subscriber.all_addresses[0].country = country
    loan_subscriber.save()

    loan_subscriber_account = BankAccount()
    loan_subscriber_account.owners.append(Party(loan_subscriber.id))
    loan_subscriber_account.start_date = None
    loan_subscriber_account.currency = currency
    loan_subscriber_account.number = get_iban()
    loan_subscriber_account.bank, = Bank.find(
        [('bic', '=', _company_bank_bic)])
    loan_subscriber_account.save()

    loan_1 = Loan()
    loan_1.lender_address = lender.addresses[0]
    loan_1.company = company
    loan_1.kind = 'fixed_rate'
    loan_1.funds_release_date = _base_contract_date
    loan_1.currency = currency
    loan_1.rate = Decimal('0.045')
    loan_1.amount = Decimal('250000')
    loan_1.duration = 200
    assert_eq(set(loan_1.extra_data.keys()), {'objet_du_pret'})
    loan_1.extra_data = {'objet_du_pret': 'terrain'}
    loan_1.save()

    loan_2 = Loan()
    loan_2.company = company
    loan_2.lender_address = lender.addresses[0]
    loan_2.kind = 'fixed_rate'
    loan_2.funds_release_date = _base_contract_date
    loan_2.currency = currency
    loan_2.rate = Decimal('0.03')
    loan_2.amount = Decimal('100000')
    loan_2.duration = 220
    loan_2.save()
    Loan.calculate_loan([loan_1.id, loan_2.id], {})

    SubscribeContract = Wizard('contract.subscribe')
    SubscribeContract.form.signature_date = _base_contract_date
    SubscribeContract.form.distributor, = DistributionNetwork.find(
        [('code', '=', 'C1010102')])
    SubscribeContract.form.commercial_product = loan_product.com_products[0]
    SubscribeContract.execute('action')

    loan_contract = Contract.find([('product.code', '=', 'loan_product')])[0]
    loan_contract.subscriber = loan_subscriber
    assert_eq(loan_contract.agent, None)
    assert_eq(loan_contract.broker,
        loan_contract.dist_network.parent_brokers[0])
    loan_contract.agent = broker_agent_flat
    process_next(loan_contract)
    assert_eq(loan_contract.extra_data_values, {'reduction_libre': '0'})
    loan_contract.extra_data_values = {'reduction_libre': '10'}
    loan_contract.covered_elements[0].current_extra_data = {
        'job_category': 'csp2',
        'co_borrower_relation': 'pacs',
        }
    ordered_loan = loan_contract.ordered_loans.new()
    ordered_loan.loan = loan_1
    ordered_loan = loan_contract.ordered_loans.new()
    ordered_loan.loan = loan_2
    process_next(loan_contract)

    SubscriptionWizard = Wizard(
        'contract.wizard.option_subscription', [loan_contract])
    SubscriptionWizard.form.default_share = Decimal('0.65')
    SubscriptionWizard.form.options[6].is_selected = True
    SubscriptionWizard.form.options[7].is_selected = True
    SubscriptionWizard.form.options[8].is_selected = True
    SubscriptionWizard.execute('update_options')
    loan_contract.reload()

    death_option = loan_contract.covered_elements[0].options[0]
    death_option.beneficiaries_clause = loan_beneficiary_clause
    unemployment_option = loan_contract.covered_elements[0].options[1]
    unemployment_option.current_extra_data = {
        'deductible_duration': '60',
        }
    loan_contract.save()
    process_next(loan_contract)
    loan_contract.document_request_lines[0].received = True
    loan_contract.document_request_lines[1].received = True
    loan_contract.save()
    process_next(loan_contract)
    loan_contract.billing_informations[0].billing_mode, = BillingMode.find(
        [('code', '=', 'yearly_sepa')])
    loan_contract.billing_informations[0].direct_debit_account = \
        loan_subscriber_account
    loan_contract.billing_informations[0].direct_debit_day = 1
    process_next(loan_contract)
    process_next(loan_contract)
    # }}}

    do_print('    Creating a funeral contract')  # {{{
    funeral_subscriber = Party()
    funeral_subscriber.name = 'DOE'
    funeral_subscriber.lang = lang
    funeral_subscriber.first_name = 'Donald'
    funeral_subscriber.birth_date = datetime.date(1951, 3, 17)
    funeral_subscriber.gender = 'male'
    funeral_subscriber.is_person = True
    funeral_subscriber.all_addresses[0].street = "\n\n40 rue d'Hauteville"
    funeral_subscriber.all_addresses[0].zip = '75010'
    funeral_subscriber.all_addresses[0].city = 'PARIS'
    funeral_subscriber.all_addresses[0].country = country
    funeral_subscriber.save()

    funeral_subscriber_account = BankAccount()
    funeral_subscriber_account.owners.append(Party(funeral_subscriber.id))
    funeral_subscriber_account.start_date = None
    funeral_subscriber_account.currency = currency
    funeral_subscriber_account.number = get_iban()
    funeral_subscriber_account.bank, = Bank.find(
        [('bic', '=', _company_bank_bic)])
    funeral_subscriber_account.save()

    SubscribeContract = Wizard('contract.subscribe')
    SubscribeContract.form.signature_date = _base_contract_date
    SubscribeContract.form.distributor = DistributionNetwork.find(
        [('code', '=', 'C1010101')])[0]
    SubscribeContract.form.commercial_product = funeral_product.com_products[0]
    SubscribeContract.execute('action')

    funeral_contract = Contract.find(
        [('product.code', '=', 'funeral_product')])[0]
    funeral_contract.subscriber = funeral_subscriber
    process_next(funeral_contract)
    funeral_contract.covered_elements.new()
    funeral_contract.covered_elements[1].party = life_subscriber
    process_next(funeral_contract)

    funeral_option = funeral_contract.covered_elements[0].options[0]
    funeral_option.current_coverage_amount = Decimal(6000)
    funeral_option.beneficiaries_clause = funeral_beneficiary_clause
    funeral_option = funeral_contract.covered_elements[1].options[0]
    funeral_option.current_coverage_amount = Decimal(4500)
    funeral_option.beneficiaries_clause = funeral_beneficiary_clause
    funeral_contract.save()

    process_next(funeral_contract)
    funeral_contract.document_request_lines[0].received = True
    funeral_contract.save()
    process_next(funeral_contract)
    process_next(funeral_contract)
    funeral_contract.billing_informations[0].billing_mode, = BillingMode.find(
        [('code', '=', 'yearly_sepa')])
    funeral_contract.billing_informations[0].direct_debit_account = \
        funeral_subscriber_account
    funeral_contract.billing_informations[0].direct_debit_day = 1
    process_next(funeral_contract)
    process_next(funeral_contract)
    # }}}

    do_print('    Creating a group life contract')  # {{{
    simple_rule, = RuleEngine.find(
        [('short_name', '=', 'benefit_simple_value')])
    complex_rule, = RuleEngine.find(
        [('short_name', '=', 'benefit_complex_value')])
    group_life_subscriber = Party()
    group_life_subscriber.is_person = False
    group_life_subscriber.name = 'Petit Charpentier'
    group_life_subscriber.lang = lang
    group_life_subscriber.all_addresses[0].street = "\n\n50 rue d'Hauteville"
    group_life_subscriber.all_addresses[0].zip = '75010'
    group_life_subscriber.all_addresses[0].city = 'PARIS'
    group_life_subscriber.all_addresses[0].country = country
    group_life_subscriber.save()

    # Create subsidiaries, employees
    subsidiaries = []
    for idx, name in enumerate(['Nord', 'Sud', 'Est', 'Ouest']):
        subsidiary = Party()
        subsidiary.is_person = False
        subsidiary.lang = lang
        subsidiary.parent_company = group_life_subscriber
        subsidiary.name = '%s %s' % (group_life_subscriber.name, name)
        subsidiary.save()

        subsidiary_account = BankAccount()
        subsidiary_account.owners.append(Party(subsidiary.id))
        subsidiary_account.currency = currency
        subsidiary_account.number = get_iban()
        subsidiary_account.bank, = Bank.find(
            [('bic', '=', _company_bank_bic)])
        subsidiary_account.start_date = None
        subsidiary_account.save()

        subsidiaries.append(subsidiary)
        for jdx in range(3):
            employee = Party()
            employee.is_person = True
            employee.name = subsidiary.name
            employee.first_name = 'Employé %i' % (jdx + 1)
            employee.gender = {0: 'male', 1: 'female'}[jdx % 2]
            employee.birth_date = datetime.date(
                1960, idx + 1, (jdx + 1) * 3 + idx)
            ssn = {'male': '1', 'female': '2'}[employee.gender] +\
                str(employee.birth_date.year)[2:] + '75461210' + str(jdx + 1) +\
                str(idx + 1)
            ssn_key = 97 - int(ssn) % 97
            employee.ssn = ssn + (str(ssn_key) if ssn_key >= 10
                else '0' + str(ssn_key))
            employee.save()

            if idx == 1 and jdx == 1:
                employee_account = BankAccount()
                employee_account.owners.append(Party(employee.id))
                employee_account.currency = currency
                employee_account.number = get_iban()
                employee_account.bank, = Bank.find(
                    [('bic', '=', _company_bank_bic)])
                employee_account.start_date = None
                employee_account.save()
                employee.addresses[0].street = '\n\n12 rue du lac'
                employee.addresses[0].zip = '75010'
                employee.addresses[0].city = 'PARIS'
                employee.addresses[0].save()

    group_life_subscriber_account = BankAccount()
    group_life_subscriber_account.owners.append(Party(group_life_subscriber.id))
    group_life_subscriber_account.currency = currency
    group_life_subscriber_account.number = get_iban()
    group_life_subscriber_account.bank, = Bank.find(
        [('bic', '=', _company_bank_bic)])
    group_life_subscriber_account.save()

    group_life_contract = Contract()
    group_life_contract.dist_network, = DistributionNetwork.find(
        [('code', '=', 'C1010101')])
    group_life_contract.subscriber = group_life_subscriber
    group_life_contract.start_date = _base_contract_date
    group_life_contract.product = group_life_product
    group_life_contract.signature_date = _base_contract_date
    group_life_contract.conditions_date = _base_contract_date
    group_life_contract.end_date = None
    group_life_contract.state = 'quote'
    group_life_contract.billing_informations.remove(
        group_life_contract.billing_informations[-1])
    group_life_contract.agent = broker_agent

    group_life_contract.covered_elements.new()
    covered = group_life_contract.covered_elements[-1]
    covered.name = 'Cadres'
    covered.item_desc = employee_category
    covered.current_extra_data = {
        'employee_type': 'cadre'}
    covered.options[-1].current_extra_data = {
        'relapse_threshold': '90'}
    assert_eq(len(covered.options[-1].versions[-1].benefits), 1)
    benefit_data = covered.options[-1].versions[-1].benefits[-1]
    benefit_data.salary_mode = 'last_12_months'
    benefit_data.net_salary_mode = True
    benefit_data.net_calculation_rule, = NetCalculationRule.find(
        [('rule.short_name', '=', 'coog_net_salary_calculation_a_payer')])
    assert benefit_data.deductible_rule is None
    benefit_data.deductible_rule = get_rule(
        'coog_franchise_relais_conventation')
    assert_eq(list(benefit_data.deductible_rule_extra_data.keys()),
        ['1_nombre_de_jours_de_franchise'])

    assert_eq(benefit_data.indemnification_rule.short_name,
        'coog_traitement_journalier_par_tranche_de_salaire')
    assert_eq(set(benefit_data.indemnification_rule_extra_data),
        {
        '1_pourcentage_ij_ta',
        '2_pourcentage_ij_tb',
        '3_pourcentage_ij_tc',
        '4_traitement_de_reference',
        '5_inclusion_du_mi_temps_therapeutique',
        '6_sans_deduction_de_l_ijss',
        '7_limiter_au_net',
        })
    benefit_data.indemnification_rule_extra_data = {
        '1_pourcentage_ij_ta': 20,
        '2_pourcentage_ij_tb': 15,
        '3_pourcentage_ij_tc': 15,
        '4_traitement_de_reference': 'salaire_brut_prime',
        '5_inclusion_du_mi_temps_therapeutique': 'tdrj_ijss_mtt',
        '6_sans_deduction_de_l_ijss': False,
        '7_limiter_au_net': True,
        }
    assert_eq(benefit_data.revaluation_rule.short_name,
        'coog_regle_standard_de_calcul_de_la_revalorisation')
    assert_eq(set(benefit_data.revaluation_rule_extra_data),
        {
        '1_reval_mode',
        '2_date_de_reference',
        '3_1ere_revalorisation',
        '4_nombre_de_jours',
        '5_frequence_revalo',
        })
    benefit_data.revaluation_rule_extra_data = {
        '1_reval_mode': 'AGIRC',
        '2_date_de_reference': 'DAT',
        '3_1ere_revalorisation': None,
        '4_nombre_de_jours': None,
        '5_frequence_revalo': 'changement_taux',
        }

    group_life_contract.covered_elements.new()
    covered = group_life_contract.covered_elements[-1]
    covered.name = 'Non cadres'
    covered.item_desc = employee_category
    covered.current_extra_data = {
        'employee_type': 'non_cadre'}
    covered.options[-1].current_extra_data = {
        'relapse_threshold': '30'}
    benefit_data = covered.options[-1].versions[-1].benefits[-1]
    benefit_data.salary_mode = 'last_12_months'
    benefit_data.net_salary_mode = True
    benefit_data.net_calculation_rule, = NetCalculationRule.find(
        [('rule.short_name', '=', 'coog_net_salary_calculation_a_payer')])
    benefit_data.deductible_rule = get_rule(
        'coog_franchise_relais_conventation')
    benefit_data.indemnification_rule_extra_data = {
        '1_pourcentage_ij_ta': 30,
        '2_pourcentage_ij_tb': 10,
        '3_pourcentage_ij_tc': 0,
        '4_traitement_de_reference': 'salaire_brut_prime',
        '5_inclusion_du_mi_temps_therapeutique': 'tdrj_ijss_mtt',
        '6_sans_deduction_de_l_ijss': False,
        '7_limiter_au_net': True,
        }
    benefit_data.revaluation_rule_extra_data = {
        '1_reval_mode': 'ARRCO',
        '2_date_de_reference': 'DAT',
        '3_1ere_revalorisation': None,
        '4_nombre_de_jours': None,
        '5_frequence_revalo': 'changement_taux',
        }

    group_life_contract.save()
    Activate = Wizard('contract.activate', [group_life_contract])
    Activate.execute('apply')
    group_life_contract.reload()

    for idx, subsidiary in enumerate(subsidiaries):
        subsidiary_covered = CoveredElement()
        subsidiary_covered.parent = group_life_contract.covered_elements[
            idx % 2]
        subsidiary_covered.party = subsidiary
        assert_eq(subsidiary_covered.item_desc.kind, 'subsidiary')
        subsidiary_covered.manual_start_date = _base_contract_date
        if idx == 3:
            subsidiary_covered.manual_end_date = _contract_rebill_date
            subsidiary_covered.end_reason, = CoveredEndReason.find(
                [('code', '=', 'revente')])
        subsidiary_covered.save()

        for jdx, employee in enumerate(Party.find([
                        ('name', '=', subsidiary.name),
                        ('is_person', '=', True)])):
            employee_covered = CoveredElement()
            employee_covered.parent = subsidiary_covered
            assert_eq(employee_covered.item_desc.kind, 'person')
            assert_eq(set(employee_covered.current_extra_data.keys()),
                {'job_start', 'job_end'})
            employee_covered.current_extra_data = {
                'job_start': _base_contract_date + relativedelta(days=-30),
                'job_end': None,
                }
            employee_covered.party = employee
            if jdx == 0:
                employee_covered.manual_start_date = _contract_rebill_date
            else:
                employee_covered.manual_start_date = _base_contract_date
            if (employee.name == 'Petit Charpentier Sud'
                    and employee.first_name == 'Employé 2'):
                employee_covered.manual_end_date = \
                    _illness_claim_end_date_1
                employee_covered.end_reason, = CoveredEndReason.find(
                    [('code', '=', 'demission')])
            employee_covered.save()
    # }}}
# }}}

if BILL_CONTRACTS:  # {{{
    do_print('\nBilling contracts')
    do_print('    Rebilling all contracts')  # {{{
    config._context['client_defined_date'] = _contract_rebill_post_date + \
        relativedelta(days=-1, months=-1)
    Contract.rebill_contracts([x.id for x in Contract.find(
                [('status', '!=', 'quote')])],
        _contract_rebill_date, _contract_rebill_date,
        _contract_rebill_post_date, config.context)
    config._context.pop('client_defined_date')
    # }}}
# }}}

if CREATE_CLAIMS:  # {{{
    do_print('\nCreating claims')
    do_print('    Loading required configuration')  # {{{

    work_interruption_claim_process, = Process.find(
        [('technical_name', '=', 'claim_work_interruption_process')])
    death_claim_process, = Process.find(
        [('technical_name', '=', 'claim_death_process')])

    claim_product_reduced_taxed, = AccountProduct.find(
        [('code', '=', 'reglement_sinistres_taxes_reduites')])
    # }}}
    do_print('    Creating a work interruption claim')  # {{{

    # Initialize claim {{{
    config._context['client_defined_date'] = _illness_claim_date
    claimant, = Party.find([
            ('name', '=', 'Petit Charpentier Sud'),
            ('first_name', '=', 'Employé 2')])
    CreateClaim = Wizard('claim.declare')
    CreateClaim.form.party = claimant
    CreateClaim.form.good_process = work_interruption_claim_process
    CreateClaim.execute('action')

    config._context['client_defined_date'] = _illness_claim_end_date_2
    claim, = Claim.find([])
    claim.declaration_date = _illness_claim_date
    assert_eq(claim.losses[0].loss_desc.code, 'temporary_work_interruption')
    claim.losses[0].event_desc, = EventDesc.find([('code', '=', 'illness')])
    claim.losses[0].start_date = _illness_claim_date
    claim.losses[0].save()
    process_next(claim)
    process_next(claim)
    # }}}

    # Create and compute salaries {{{
    SalaryWizard = Wizard('claim.salaries_computation', [claim])
    for idx, period in enumerate(SalaryWizard.form.periods):
        period.gross_salary = Decimal(2143) + Decimal('14.27') * idx
        if idx == 6:
            period.salary_bonus = Decimal('3124.11')
    SalaryWizard.execute('process')
    assert_eq(SalaryWizard.form.rates[0].extra_data.name,
        '1_coog_urssaf_1')
    SalaryWizard.form.rates[0].ta = Decimal('0.75')
    SalaryWizard.form.rates[0].tb = Decimal('0.23')
    assert_eq(SalaryWizard.form.rates[1].extra_data.name,
        '1_coog_urssaf_2')
    SalaryWizard.form.rates[1].ta = Decimal('1.5')
    SalaryWizard.form.rates[1].tb = Decimal('1.6')
    assert_eq(SalaryWizard.form.rates[2].extra_data.name,
        '1_coog_urssaf_3')
    SalaryWizard.form.rates[2].ta = Decimal('6.9')
    SalaryWizard.form.rates[2].ta = Decimal('7.43')
    assert_eq(SalaryWizard.form.rates[3].extra_data.name,
        '1_coog_urssaf_4')
    SalaryWizard.form.rates[3].ta = Decimal('0.35')
    SalaryWizard.form.rates[3].ta = Decimal('0.67')
    assert_eq(SalaryWizard.form.rates[4].extra_data.name,
        '2_coog_retraite_1')
    SalaryWizard.form.rates[4].ta = Decimal('0.8')
    SalaryWizard.form.rates[4].ta = Decimal('1.52')
    assert_eq(SalaryWizard.form.rates[5].extra_data.name,
        '2_coog_retraite_2')
    SalaryWizard.form.rates[5].ta = Decimal('3.1')
    SalaryWizard.form.rates[5].ta = Decimal('3.21')
    assert_eq(SalaryWizard.form.rates[6].extra_data.name,
        '3_coog_prevoyance_1')
    SalaryWizard.form.rates[6].ta = Decimal(0)
    SalaryWizard.form.rates[6].tb = Decimal('1.1')
    assert_eq(SalaryWizard.form.rates[7].extra_data.name,
        '3_coog_prevoyance_2')
    SalaryWizard.form.rates[7].ta = Decimal(0)
    SalaryWizard.form.rates[7].tb = Decimal('2.1')
    assert_eq(SalaryWizard.form.rates[8].extra_data.name,
        '4_coog_chomage_1')
    SalaryWizard.form.rates[8].ta = Decimal('2.4')
    SalaryWizard.form.rates[8].tb = Decimal('3.1')
    assert_eq(SalaryWizard.form.rates[9].extra_data.name,
        '4_coog_chomage_2')
    SalaryWizard.form.rates[9].ta = Decimal(0)
    SalaryWizard.form.rates[9].tb = Decimal(0)
    assert_eq(SalaryWizard.form.rates[10].extra_data.name,
        '5_coog_charges_patronales_prevoyance')
    SalaryWizard.form.rates[10].ta = Decimal('1.428')
    SalaryWizard.form.rates[10].tb = Decimal('1.72')
    assert_eq(SalaryWizard.form.rates[11].extra_data.name,
        '6_coog_charges_patronales_sante_taux')
    SalaryWizard.form.rates[11].ta = Decimal(0)
    SalaryWizard.form.rates[11].tb = Decimal(0)
    assert_eq(SalaryWizard.form.rates[12].extra_data.name,
        '6_coog_charges_salariales_sante_taux')
    SalaryWizard.form.rates[12].ta = Decimal(0)
    SalaryWizard.form.rates[12].tb = Decimal(0)

    assert_eq(SalaryWizard.form.fixed_amounts[0].extra_data.name,
        '1_coog_charges_salariales_mutuelle')
    SalaryWizard.form.fixed_amounts[0].fixed_amount = Decimal('46.34')
    assert_eq(SalaryWizard.form.fixed_amounts[1].extra_data.name,
        '2_coog_charges_patronales_sante_montant')
    SalaryWizard.form.fixed_amounts[1].fixed_amount = Decimal('46.34')
    SalaryWizard.execute('compute')
    claim.reload()
    for salary, net in zip(claim.losses[0].services[0].salary, [
                Decimal('1547.47'), Decimal('1558.11'), Decimal('1568.74'),
                Decimal('1579.38'), Decimal('1590.02'), Decimal('1600.66'),
                Decimal('4134.53'), Decimal('1621.93'), Decimal('1632.57'),
                Decimal('1643.21'), Decimal('1653.85'), Decimal('1664.48')]):
        assert_eq(salary.net_salary, net)
    process_next(claim)
    # }}}

    # First indemnification period (paid to the company) {{{
    CreateIndemnification = Wizard('claim.create_indemnification', [claim])
    assert_eq(CreateIndemnification.form.beneficiary,
        Party.find([('name', '=', 'Petit Charpentier Sud'),
                ('is_person', '=', False)])[0])
    assert_eq(set(CreateIndemnification.form.extra_data.keys()),
        {'date_d_effet_d_indemnisation', 'ijss'})
    CreateIndemnification.form.extra_data = {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('15.00'),
        }
    CreateIndemnification.form.end_date = _illness_claim_end_date_1
    CreateIndemnification.execute('calculate')
    CreateIndemnification.execute('regularisation')
    CreateIndemnification.execute('validate_scheduling')
    claim.reload()

    assert_eq(claim.losses[0].services[0].indemnifications[0].total_amount,
        Decimal('303.36'))
    deductible_line = claim.losses[0].services[0].indemnifications[0].details[0]
    assert_eq(deductible_line.kind, 'deductible')
    assert_eq(deductible_line.nb_of_unit, 30)
    assert_eq(deductible_line.unit, 'day')
    assert_eq(deductible_line.base_amount, Decimal(0))
    assert_eq(deductible_line.amount_per_unit, Decimal(0))
    assert_eq(deductible_line.amount, Decimal(0))
    benefit_line = claim.losses[0].services[0].indemnifications[0].details[1]
    assert_eq(benefit_line.kind, 'benefit')
    assert_eq(benefit_line.nb_of_unit, 32)
    assert_eq(benefit_line.unit, 'day')
    assert_eq(benefit_line.base_amount, Decimal('9.48'))
    assert_eq(benefit_line.amount_per_unit, Decimal('9.48'))
    assert_eq(benefit_line.amount, Decimal('303.36'))
    # }}}

    # Second indemnification period (paid to the party, with pasrau) {{{
    # Create fake pasrau value for testing
    default_pasrau = DefaultPasrauRate()
    default_pasrau.start_date = datetime.date(2018, 1, 1)
    default_pasrau.end_date = datetime.date(2019, 1, 1)
    default_pasrau.income_lower_bound = Decimal(0)
    default_pasrau.income_higher_bound = Decimal(1000000)  # Arbitrarly high
    default_pasrau.region = 'metropolitan'
    default_pasrau.rate = Decimal('0.07')
    default_pasrau.save()

    # First test. This case makes sure the indemnification amount and the
    # details amount are consistent (avoid regression after #10992)
    CreateIndemnification = Wizard('claim.create_indemnification', [claim])
    assert_eq(CreateIndemnification.form.beneficiary, claim.claimant)
    assert_eq(CreateIndemnification.form.extra_data, {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('15.00'),
        })
    assert_eq(CreateIndemnification.form.start_date,
        _illness_claim_end_date_1 + relativedelta(days=1))
    CreateIndemnification.form.extra_data = {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('12.50'),
        }
    CreateIndemnification.form.end_date = _illness_claim_end_date_2
    CreateIndemnification.form.product = claim_product_reduced_taxed
    CreateIndemnification.execute('calculate')
    CreateIndemnification.execute('regularisation')
    CreateIndemnification.execute('end')
    claim.reload()

    benefit_line = claim.losses[0].services[0].indemnifications[1].details[0]
    assert_eq(benefit_line.kind, 'benefit')
    assert_eq(benefit_line.nb_of_unit, 14)
    assert_eq(benefit_line.unit, 'day')
    assert_eq(benefit_line.base_amount, Decimal('11.98'))
    assert_eq(benefit_line.amount_per_unit, Decimal('11.98'))
    assert_eq(benefit_line.amount, Decimal('167.72'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].amount,
        Decimal('167.72'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].total_amount,
        Decimal('149.22'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].tax_amount,
        Decimal('-18.50'))

    # Recompute with another configuration
    Indemnification.delete([claim.losses[0].services[0].indemnifications[1]])

    CreateIndemnification = Wizard('claim.create_indemnification', [claim])
    assert_eq(CreateIndemnification.form.beneficiary, claim.claimant)
    assert_eq(CreateIndemnification.form.extra_data, {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('12.50'),
        })
    assert_eq(CreateIndemnification.form.start_date,
        _illness_claim_end_date_1 + relativedelta(days=1))
    CreateIndemnification.form.extra_data = {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('15.00'),
        }
    CreateIndemnification.form.end_date = _illness_claim_end_date_2
    CreateIndemnification.form.product = claim_product_reduced_taxed
    CreateIndemnification.execute('calculate')
    CreateIndemnification.execute('regularisation')
    CreateIndemnification.execute('end')
    claim.reload()

    benefit_line = claim.losses[0].services[0].indemnifications[1].details[0]
    assert_eq(benefit_line.kind, 'benefit')
    assert_eq(benefit_line.nb_of_unit, 14)
    assert_eq(benefit_line.unit, 'day')
    assert_eq(benefit_line.base_amount, Decimal('9.48'))
    assert_eq(benefit_line.amount_per_unit, Decimal('9.48'))
    assert_eq(benefit_line.amount, Decimal('132.72'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].amount,
        Decimal('132.72'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].total_amount,
        Decimal('118.08'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].tax_amount,
        Decimal('-14.64'))

    # Recompute and switch to personalized pasrau rate
    Indemnification.delete([claim.losses[0].services[0].indemnifications[1]])
    DefaultPasrauRate.delete([default_pasrau])
    claim.reload()

    party_pasrau = PartyPasrauRate()
    party_pasrau.effective_date = _illness_claim_end_date_1
    party_pasrau.origin = 'manual'
    party_pasrau.party = claimant
    party_pasrau.pasrau_tax_rate = Decimal('0.144')
    party_pasrau.business_id = 'Some Business Id'
    party_pasrau.save()

    CreateIndemnification = Wizard('claim.create_indemnification', [claim])
    assert_eq(CreateIndemnification.form.beneficiary, claim.claimant)
    assert_eq(CreateIndemnification.form.extra_data, {
        'date_d_effet_d_indemnisation': _illness_claim_date
        + relativedelta(days=30),
        'ijss': Decimal('15.00'),
        })
    assert_eq(CreateIndemnification.form.start_date,
        _illness_claim_end_date_1 + relativedelta(days=1))
    CreateIndemnification.form.end_date = _illness_claim_end_date_2
    CreateIndemnification.form.product = claim_product_reduced_taxed
    CreateIndemnification.execute('calculate')
    CreateIndemnification.execute('regularisation')
    CreateIndemnification.execute('validate_scheduling')
    claim.reload()

    benefit_line = claim.losses[0].services[0].indemnifications[1].details[0]
    assert_eq(benefit_line.kind, 'benefit')
    assert_eq(benefit_line.nb_of_unit, 14)
    assert_eq(benefit_line.unit, 'day')
    assert_eq(benefit_line.base_amount, Decimal('9.48'))
    assert_eq(benefit_line.amount_per_unit, Decimal('9.48'))
    assert_eq(benefit_line.amount, Decimal('132.72'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].total_amount,
        Decimal('108.63'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].tax_amount,
        Decimal('-24.09'))
    assert_eq(claim.losses[0].services[0].indemnifications[1].amount,
        Decimal('132.72'))
    process_next(claim)
    # }}}

    # Finalize claim {{{
    claim.losses[0].end_date = _illness_claim_end_date_2
    claim.losses[0].closing_reason, = ClaimClosingReason.find(
        [('code', '=', 'back_to_work')])
    claim.losses[0].save()
    process_next(claim)
    CloseClaim = Wizard('claim.close', [claim])
    CloseClaim.form.sub_status, = ClaimSubStatus.find([('code', '=', 'paid')])
    CloseClaim.execute('apply_sub_status')

    config._context.pop('client_defined_date')
    # }}}

    # Check invoices {{{
    invoice_1 = (claim.losses[0].services[0].indemnifications[0]
        .invoice_line_details[0].invoice_line.invoice)
    assert_eq(invoice_1.base_amount, Decimal('303.36'))
    assert_eq(invoice_1.total_amount, Decimal('303.36'))
    assert_eq(invoice_1.tax_amount, Decimal(0))
    assert_eq(len(invoice_1.taxes), 0)

    invoice_2 = (claim.losses[0].services[0].indemnifications[1]
        .invoice_line_details[0].invoice_line.invoice)
    assert_eq(invoice_2.base_amount, Decimal('132.72'))
    assert_eq(invoice_2.total_amount, Decimal('108.63'))
    assert_eq(invoice_2.tax_amount, Decimal('-24.09'))
    assert_eq(len(invoice_2.taxes), 3)
    per_tax = {x.tax.name: x for x in invoice_2.taxes}
    assert_eq(per_tax['CRDS'].amount, Decimal('-0.66'))  # 0.5 %
    assert_eq(per_tax['CSG déductible'].amount, Decimal('-5.04'))  # 3.8 %
    # 14.4 % based on base_amount - CSG => 132.72 * (1 - 0.038)
    assert_eq(per_tax['pasrau'].amount, Decimal('-18.39'))
    # }}}
    # }}}

    account_move_line_pasrau_rate, = MoveLinePasrauRate.find([])
    assert_eq(account_move_line_pasrau_rate.move_line.amount,
        Decimal('-18.39'))
    assert_eq(account_move_line_pasrau_rate.pasrau_rate,
        Decimal('0.144'))
    assert_eq(account_move_line_pasrau_rate.pasrau_rate_kind, 'manual')
    assert_eq(account_move_line_pasrau_rate.pasrau_rate_business_id,
        'Some Business Id')

    do_print('    Creating a death claim')  # {{{
    config._context['client_defined_date'] = _death_claim_date
    claimant, = Party.find([('name', '=', 'DOE'), ('first_name', '=', 'John')])
    CreateClaim = Wizard('claim.declare')
    CreateClaim.form.party = claimant
    CreateClaim.form.good_process = death_claim_process
    CreateClaim.form.legal_entity = None
    CreateClaim.execute('action')
    claim, = Claim.find([('claimant', '=', claimant.id)])
    claim.declaration_date = _death_claim_date
    claim.losses[0].loss_desc, = LossDesc.find([('code', '=', 'death')])
    claim.losses[0].event_desc, = EventDesc.find([('code', '=', 'suicide')])
    claim.losses[0].start_date = _death_claim_date
    claim.losses[0].save()
    process_next(claim)

    assert_eq(claim.losses[0].services[0].eligibility_status, 'refused')
    process_previous(claim)
    claim.losses[0].click('draft')
    claim.losses[0].event_desc, = EventDesc.find([('code', '=', 'illness')])
    claim.losses[0].save()
    process_next(claim)

    assert_eq(claim.losses[0].services[0].eligibility_status, 'accepted')
    service = claim.losses[0].services[0]
    service.beneficiaries.new()
    service.beneficiaries[-1].party, = Party.find([('name', '=', 'DOE'),
            ('first_name', '=', 'Jane')])
    service.beneficiaries[-1].share = Decimal(1)
    service.beneficiaries[-1].identification_date = _death_claim_date
    service.beneficiaries[-1].click('identify')
    service.beneficiaries[-1].save()
    process_next(claim)

    CreateIndemnification = Wizard('claim.create_indemnification', [claim])
    CreateIndemnification.form.beneficiary, = Party.find([
            ('name', '=', 'DOE'), ('first_name', '=', 'Jane')])
    CreateIndemnification.execute('calculate')
    CreateIndemnification.execute('regularisation')
    CreateIndemnification.execute('validate_scheduling')

    claim.reload()
    assert_eq(claim.losses[0].services[0].indemnifications[0].total_amount,
        Decimal(20000))
    process_next(claim)
    process_next(claim)

    CloseClaim = Wizard('claim.close', [claim])
    CloseClaim.form.sub_status, = ClaimSubStatus.find([('code', '=', 'paid')])
    CloseClaim.execute('apply_sub_status')
    config._context.pop('client_defined_date')
    # }}}
# }}}

if GENERATE_REPORTINGS:  # {{{
    do_print('\nGenerating reportings')
    do_print('    Paying contract invoices')  # {{{
    config._context['client_defined_date'] = _contract_payment_date

    # Ideally we would use the payment wizard on invoices, but we cannot force
    # the date in the past because it compares to Date()
    lines = MoveLine.find([
            ['OR',
                ('account.type.receivable', '=', True),
                ('account.type.payable', '=', True),
            ],
            ('party', '!=', None), ('reconciliation', '=', None),
            ('payment_amount', '!=', 0), ('move_state', '=', 'posted'),
            ['OR', ('debit', '>', 0), ('credit', '<', 0)]])

    PayLines = Wizard('account.payment.creation', lines)
    assert_eq(PayLines.form.total_amount, Decimal('2321.88'))
    assert_eq(PayLines.form.payment_date, _contract_payment_date)
    PayLines.form.journal, = PaymentJournal.find([
            ('name', '=', 'Sepa')])
    PayLines.execute('create_payments')

    payments = Payment.find([('kind', '=', 'receivable')])
    assert_eq(len(payments), 4)
    assert_eq({x.state for x in payments}, {'approved'})
    assert_eq({x.date for x in payments}, {_contract_payment_date})
    assert_eq(sum(x.amount for x in payments), Decimal('2321.88'))

    ProcessPayments = Wizard('account.payment.process', payments)
    ProcessPayments.execute('pre_process')

    group, = PaymentGroup.find([('kind', '=', 'receivable')])
    assert_eq(group.state, 'processing')
    assert_eq(group.amount, Decimal('2321.88'))
    assert_eq(group.payment_date_min, _contract_payment_date)

    group.click('acknowledge')

    payments = Payment.find([('kind', '=', 'receivable')])
    assert_eq({x.state for x in payments}, {'succeeded'})
    assert_eq(all(x.line.reconciliation for x in payments), True)
    assert_eq({x.clearing_move.date for x in payments},
        {_contract_payment_date})
    assert_eq({x.clearing_move.state for x in payments}, {'posted'})

    invoices = Invoice.find([('state', '!=', 'cancel'), ('start', '!=', None),
            ('business_kind', '=', 'contract_invoice')])
    assert_eq(len(invoices), 4)
    assert_eq({x.state for x in invoices}, {'paid'})

    config._context.pop('client_defined_date')
    # }}}

    do_print('    Paying claim invoices')  # {{{
    config._context['client_defined_date'] = _illness_claim_end_date_2

    # Ideally we would use the payment wizard on invoices, but we cannot force
    # the date in the past because it compares to Date()
    lines = MoveLine.find([
            ['OR',
                ('account.type.receivable', '=', True),
                ('account.type.payable', '=', True),
            ],
            ('party', '!=', None), ('reconciliation', '=', None),
            ('payment_amount', '!=', 0), ('move_state', '=', 'posted'),
            ['OR', ('debit', '<', 0), ('credit', '>', 0)]])

    PayLines = Wizard('account.payment.creation', lines)
    assert_eq(PayLines.form.total_amount, Decimal('20411.99'))
    assert_eq(PayLines.form.payment_date, _illness_claim_end_date_2)
    PayLines.form.journal, = PaymentJournal.find([
            ('name', '=', 'Sepa')])

    # Warning because all lines are not on the same date
    test_error(UserWarning, PayLines.execute, 'create_payments')

    line_to_update_date, = MoveLine.find([('credit', '=', Decimal(20000))])
    warning = Warning()
    warning.always = False
    warning.user = User(config.user)
    warning.name = 'updating_payment_date_account.move.line,%s' % str(
        line_to_update_date.id)
    warning.save()

    PayLines.execute('create_payments')

    payments = Payment.find([('kind', '=', 'payable')])
    assert_eq(len(payments), 3)
    assert_eq({x.state for x in payments}, {'approved'})
    assert_eq({x.date for x in payments}, {_illness_claim_end_date_2})
    assert_eq(sum(x.amount for x in payments), Decimal('20411.99'))

    ProcessPayments = Wizard('account.payment.process', payments)
    ProcessPayments.execute('pre_process')

    group, = PaymentGroup.find([('kind', '=', 'payable')])
    assert_eq(group.state, 'processing')
    assert_eq(group.amount, Decimal('20411.99'))
    assert_eq(group.payment_date_min, _illness_claim_end_date_2)

    group.click('acknowledge')

    payments = Payment.find([('kind', '=', 'payable')])
    assert_eq({x.state for x in payments}, {'succeeded'})
    assert_eq(all(x.line.reconciliation for x in payments), True)
    assert_eq({x.clearing_move.date for x in payments},
        {_illness_claim_end_date_2})
    assert_eq({x.clearing_move.state for x in payments}, {'posted'})

    invoices = Invoice.find([('state', '!=', 'cancel'),
            ('business_kind', '=', 'claim_invoice')])
    assert_eq(len(invoices), 3)
    assert_eq({x.state for x in invoices}, {'paid'})

    config._context.pop('client_defined_date')
    # }}}

    do_print('    Generating commission invoices')  # {{{
    CommissionCreate = Wizard('commission.create_invoice')
    CommissionCreate.form.from_ = _base_contract_date
    CommissionCreate.form.to = _commission_invoice_date
    CommissionCreate.execute('create_')

    for invoice in Invoice.find(
            [('business_kind', '=', 'broker_invoice')]):
        ReportCreation = Wizard('report.create', [invoice])
        ReportCreation.execute('generate')
    # }}}

    do_print('    Generating insurer invoices')  # {{{
    InsurerInvoiceCreate = Wizard('account.invoice.create.insurer_slip')
    InsurerInvoiceCreate.form.until_date = _commission_invoice_date
    InsurerInvoiceCreate.form.insurers.append(Party(insurer.party.id))
    InsurerInvoiceCreate.form.notice_kind = 'options'
    InsurerInvoiceCreate.execute('create_')

    insurer_invoice, = Invoice.find(
        [('business_kind', '=', 'insurer_invoice')])
    assert_eq(insurer_invoice.total_amount, Decimal('1857.5'))
    ReportCreation = Wizard('report.create', [insurer_invoice])
    ReportCreation.execute('generate')
    Invoice.delete([insurer_invoice])

    InsurerInvoiceCreate = Wizard('account.invoice.create.insurer_slip')
    InsurerInvoiceCreate.form.until_date = _commission_invoice_date
    InsurerInvoiceCreate.form.insurers.append(Party(insurer.party.id))
    InsurerInvoiceCreate.form.notice_kind = 'benefits'
    InsurerInvoiceCreate.execute('create_')

    claim_insurer_invoice, = Invoice.find(
        [('business_kind', '=', 'claim_insurer_invoice')])
    assert_eq(claim_insurer_invoice.total_amount, Decimal('20436.08'))
    Invoice.delete([claim_insurer_invoice])

    insurer.group_insurer_invoices = True
    insurer.save()
    InsurerInvoiceCreate = Wizard('account.invoice.create.insurer_slip')
    InsurerInvoiceCreate.form.until_date = _commission_invoice_date
    InsurerInvoiceCreate.form.insurers.append(Party(insurer.party.id))
    InsurerInvoiceCreate.form.notice_kind = 'all'
    InsurerInvoiceCreate.execute('create_')

    insurer_invoice, = Invoice.find(
        [('business_kind', '=', 'all_insurer_invoices')])
    assert_eq(insurer_invoice.total_amount, Decimal('-18578.58'))
    # }}}

    do_print('    Generating slip')  # {{{
    slip_configuration, = InvoiceSlipConfiguration.find([])
    CreateSlip = Wizard('account.invoice.create.slip', [slip_configuration])
    assert_eq(CreateSlip.form.party, slip_configuration.party)
    assert_eq(CreateSlip.form.accounts, slip_configuration.accounts)
    assert_eq(CreateSlip.form.slip_kind, slip_configuration.slip_kind)
    assert_eq(CreateSlip.form.journal, slip_configuration.journal)
    CreateSlip.form.slip_date = _slip_generation_date
    CreateSlip.execute('open_slip')

    slip, = Invoice.find([('business_kind', '=', 'pasrau')])
    assert_eq(slip.total_amount, Decimal('24.09'))

    if not TESTING:
        # Configuration may not be set, so we must handle the warning
        warning = Warning()
        warning.always = False
        warning.user = User(1)
        warning.name = 'undefined_dsn_section'
        warning.save()

    slip.click('post')

    if TESTING:
        # The message should have been generated
        messages = DSNMessage.find([])
        assert_eq(len(messages), 1)
        generated_pasrau_message = messages[0].text_message.split('\n')
        path = os.path.join(os.path.dirname(__file__), 'test_data',
            'pasrau_dsn.txt')
        with open(path, 'rb') as f:
            test_pasrau_message = f.read().decode('latin1').split('\n')

        assert_eq(len(generated_pasrau_message), len(test_pasrau_message))
        assert_eq(len(generated_pasrau_message), 58)
        # there is a carriage return at the end of the file
        # so we have an emply line at the of the list
        for message_line, control_line in zip(generated_pasrau_message,
                test_pasrau_message):
            if not message_line and not control_line:
                continue
            section, content = message_line.split(',')
            if section in ("S20.G00.05.007", "S21.G00.50.001"):
                # file date and reconciliation date
                today_str = datetime.date.today().strftime('%d%m%Y')
                assert message_line.split(',')[-1] == \
                    '\'' + today_str + '\''
            else:
                assert_eq(message_line.strip(), control_line.strip())

    # }}}

    if TESTING:
        do_print('    Testing non contract payment rejection')  # {{{
        payable_reject_reason, = PaymentJournalRejectReason.find([
                ('code', '=', 'ALL'), ('payment_kind', '=', 'payable'),
                ('process_method', '=', 'sepa')])
        to_reject, = Payment.find([('amount', '=', 20000)])
        RejectPayment = Wizard('account.payment.manual_payment_fail',
            [to_reject])
        RejectPayment.form.reject_reason = payable_reject_reason
        RejectPayment.execute('fail_payments')

        to_reject.reload()
        assert_eq(to_reject.state, 'failed')
        # }}}
# }}}

if TEST_APIS:  # {{{

    def run_api(api, file_path, parameters, context):
        with open(os.path.abspath(
                    os.path.join(
                        os.path.normpath(__file__), '..', file_path)),
                'r') as f:
            switch_user('coog_api_user')
            api_class, api_name = api.rsplit('.', 1)
            data = json.loads(f.read() % parameters)
            result = getattr(Model.get(api_class), api_name)(data, context, {})
            switch_user('admin')
            return result

    do_print('\nTesting APIs')
    do_print('    Loading Configuration')  # {{{
    questionnaire_sante_prev, = Questionnaire.find([
            ('code', '=', 'sante_et_prevoyance_mpd')])
    network, = DistributionNetwork.find([('code', '=', 'C1010102')])
    lender, = Party.find([('name', '=', _lender_name)])
    # }}}

    do_print('    Updating API User')  # {{{
    api_user, = User.find([('login', '=', 'coog_api_user')])
    api_user.password = 'poiuytreza'
    api_user.save()
    # }}}

    do_print('    Creating a contract')  # {{{
    result = run_api(
        'api.contract.subscribe_contracts',
        'api_files/compute_questionnaire.json',
        {
            'part_1_id': questionnaire_sante_prev.parts[0].id,
            'part_2_id': questionnaire_sante_prev.parts[1].id,
            },
        {'_debug_server': True, 'dist_network': network.id})

    # Simply check this is not an error.
    assert_eq('contracts' in result, True)

    result = run_api(
        'api.contract.subscribe_contracts',
        'api_files/subscribe_loan_contract.json',
        {
            'lender_address_id': lender.addresses[0].id,
            },
        {'_debug_server': True, 'dist_network': network.id})

    # Simply check this is not an error.
    assert_eq('contracts' in result, True)
    # }}}
# }}}

# vim:fdm=marker
