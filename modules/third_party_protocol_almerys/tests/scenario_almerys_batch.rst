======================================
Third Party Right Management Scenario
======================================

Imports::

    >>> import datetime as dt
    >>> import pathlib
    >>> import tempfile
    >>> import os
    >>> import sys
    >>> import datetime
    >>> from subprocess import Popen as popen
    >>> from lxml import etree
    >>> from proteus import Model, Wizard
    >>> from trytond.tools import file_open
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.party_cog.tests.tools import create_party_person, \
    ...     create_party_company
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.coog_core.test_framework import execute_test_case
    >>> from trytond.modules.third_party_protocol_almerys import batch as \
    ...     almerys_batch_2

Remove previous batch files generated::

    >>> temp_dir = tempfile.gettempdir()
    >>> batch_dir = pathlib.Path(temp_dir) / 'third_party_protocol_batch_almerys'
    >>> for batch_file in batch_dir.glob('*.xml'):
    ...     batch_file.unlink()

Install Modules::

    >>> config = activate_modules(['third_party_protocol_almerys', 'batch_launcher'],
    ...     cache_file_name='third_party_protocol_almerys_scen_1')

Create country::

    >>> _ = create_country()

Create currency::

    >>> currency = get_currency(code='EUR')

Create Company::

    >>> _ = create_company(currency=currency)

Set authorizations::

    >>> execute_test_case('authorizations_test_case')
    >>> company = get_company()

Create Fiscal Year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create Account Kind::

    >>> AccountKind = Model.get('account.account.type')
    >>> product_account_kind = AccountKind()
    >>> product_account_kind.name = 'Product Account Kind'
    >>> product_account_kind.company = company
    >>> product_account_kind.save()
    >>> receivable_account_kind = AccountKind()
    >>> receivable_account_kind.name = 'Receivable Account Kind'
    >>> receivable_account_kind.company = company
    >>> receivable_account_kind.save()
    >>> payable_account_kind = AccountKind()
    >>> payable_account_kind.name = 'Payable Account Kind'
    >>> payable_account_kind.company = company
    >>> payable_account_kind.save()

Create Account::

    >>> Account = Model.get('account.account')
    >>> product_account = Account()
    >>> product_account.name = 'Product Account'
    >>> product_account.code = 'product_account'
    >>> product_account.kind = 'revenue'
    >>> product_account.type = product_account_kind
    >>> product_account.company = company
    >>> product_account.save()
    >>> receivable_account = Account()
    >>> receivable_account.name = 'Account Receivable'
    >>> receivable_account.code = 'account_receivable'
    >>> receivable_account.kind = 'receivable'
    >>> receivable_account.party_required = True
    >>> receivable_account.reconcile = True
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.kind = 'payable'
    >>> payable_account.party_required = True
    >>> payable_account.type = payable_account_kind
    >>> payable_account.company = company
    >>> payable_account.save()

Create Insurer::

    >>> company = get_company()
    >>> currency = get_currency(code='EUR')
    >>> Country = Model.get('country.country')
    >>> france, = Country.find([('code', '=', 'FR')])
    >>> Insurer = Model.get('insurer')
    >>> Party = Model.get('party.party')
    >>> Account = Model.get('account.account')
    >>> insurer = Insurer()
    >>> insurer.party = Party()
    >>> insurer.party.name = 'Insurer'
    >>> insurer.party.account_receivable = Account(receivable_account.id)
    >>> insurer.party.account_payable = Account(payable_account.id)
    >>> insurer_address = insurer.party.all_addresses[0]
    >>> insurer_address.street = 'Adresse Inconnue'
    >>> insurer_address.zip = '99999'
    >>> insurer_address.city = 'Bioul'
    >>> insurer_address.country = france
    >>> insurer.party.save()
    >>> insurer.save()

Create Item Description::

    >>> ItemDescription = Model.get('offered.item.description')
    >>> item_description = ItemDescription()
    >>> item_description.name = 'Test Item Description'
    >>> item_description.code = 'test_item_description'
    >>> item_description.kind = 'person'
    >>> item_description.save()

Create Product::

    >>> SequenceType = Model.get('ir.sequence.type')
    >>> Sequence = Model.get('ir.sequence')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Product = Model.get('offered.product')
    >>> SubStatus = Model.get('contract.sub_status')
    >>> sequence_code = SequenceType()
    >>> sequence_code.name = 'Product sequence'
    >>> sequence_code.code = 'contract'
    >>> sequence_code.company = company
    >>> sequence_code.save()
    >>> contract_sequence = Sequence()
    >>> contract_sequence.name = 'Contract Sequence'
    >>> contract_sequence.code = sequence_code.code
    >>> contract_sequence.company = company
    >>> contract_sequence.save()
    >>> quote_sequence_code = SequenceType()
    >>> quote_sequence_code.name = 'Product sequence'
    >>> quote_sequence_code.code = 'quote'
    >>> quote_sequence_code.company = company
    >>> quote_sequence_code.save()
    >>> quote_sequence = Sequence()
    >>> quote_sequence.name = 'Quote Sequence'
    >>> quote_sequence.code = quote_sequence_code.code
    >>> quote_sequence.company = company
    >>> quote_sequence.save()
    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.start_date = dt.date(2014, 1, 1)
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.subscription_behaviour = 'optional'
    >>> coverage.account_for_billing = Model.get('account.account')(product_account.id)
    >>> coverage.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = dt.date(2014, 1, 1)
    >>> product.coverages.append(coverage)
    >>> product.save()

Create Subscriber::

    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> bnp = create_party_company(name='BNP')
    >>> bnp.save()
    >>> bank = Bank(party=bnp, bic='BNPAFRPPXXX')
    >>> bank.save()
    >>> subscriber = create_party_person()
    >>> subscriber.almerys_joignabilite_adresse_media = 'EMAIL'
    >>> cm = subscriber.contact_mechanisms.new()
    >>> cm.type = 'email'
    >>> cm.value = 'subscriber@domain.test'
    >>> subscriber.save()
    >>> bank_account = BankAccount()
    >>> bank_account.number = 'FR14 2004 1010 0505 0001 3M02 606'
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(subscriber)
    >>> bank_account.currency = currency
    >>> bank_account.save()

Create a manager::

    >>> party_manager = create_party_company()

Create Protocol::

    >>> Rule = Model.get('rule_engine')
    >>> RuleContext = Model.get('rule_engine.context')
    >>> ThirdPartyManager = Model.get('third_party_manager')
    >>> Protocol = Model.get('third_party_manager.protocol')
    >>> EventType = Model.get('event.type')
    >>> manager = ThirdPartyManager()
    >>> manager.party = party_manager
    >>> manager.save()
    >>> context = RuleContext(1)
    >>> rule = Rule()
    >>> rule.short_name = 'test'
    >>> rule.name = 'Test Rule'
    >>> rule.algorithm = """ return {
    ...     'add_period': code_evenement() not in {'void_contract', 'hold_contract'},
    ...     'third_party_protocol_almerys_reference_produit': 'PRODUCT',
    ...     'third_party_protocol_almerys_ref_interne': 'REF INTERNE',
    ...     'third_party_protocol_almerys_ref_courtier': 'REF COURTIER',
    ...     'third_party_protocol_almerys_ref_entreprise': 'REF ENTREPRISE',
    ...     'third_party_protocol_almerys_num_contrat_collectif': 'CONTRAT COLLECTIF',
    ...     'third_party_protocol_almerys_ref_site': 'REF SITE',
    ...     'third_party_protocol_almerys_ref_gestionnaire': 'REF GESTIONNAIRE',
    ...     }"""
    >>> rule.status = 'validated'
    >>> rule.context = context
    >>> rule.save()
    >>> protocol = Protocol()
    >>> protocol.name = "Basic Protocol"
    >>> protocol.code = "BASIC"
    >>> protocol.technical_protocol = 'almerys'
    >>> protocol.almerys_ss_groupe = 'ss-groupe'
    >>> protocol.almerys_libelle_ss_groupe = 'SOUS-GROUPE'
    >>> protocol.almerys_support_tp = True
    >>> protocol.third_party_manager = manager
    >>> watched_events = protocol.watched_events.find([
    ...         ('code', 'in', ['activate_contract', 'hold_contract',
    ...                 'unhold_contract', 'void_contract']),
    ...         ])
    >>> protocol.watched_events.extend(watched_events)
    >>> protocol.rule = rule
    >>> protocol.save()
    >>> almerys_sequence = Sequence(
    ...     name='Almerys', code='third_party_protocol.almerys.v3')
    >>> almerys_sequence.save()
    >>> AlmerysConfig = Model.get('third_party_protocol.almerys.configuration')
    >>> almerys_config = AlmerysConfig(1)
    >>> almerys_config.customer_number = '007'
    >>> almerys_config.customer_label = 'Customer Label'
    >>> almerys_config.number_sequence_v3 = almerys_sequence
    >>> almerys_config.protocol_version = '3'
    >>> almerys_config.autonomous = True
    >>> almerys_config.save()

Distribution Network::

    >>> DistributionNetwork = Model.get('distribution.network')
    >>> dist_network = DistributionNetwork()
    >>> dist_network.name = "Distribution"
    >>> dist_network.party = create_party_company("I Distribute")
    >>> dist_network.save()

Create Contract::

    >>> Contract = Model.get('contract')
    >>> protocol = Model.get('third_party_manager.protocol')(protocol.id)
    >>> coverage = Model.get('offered.option.description')(coverage.id)
    >>> item_description = Model.get('offered.item.description')(item_description.id)
    >>> contract = Contract()
    >>> company = Model.get('company.company')(company.id)
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.dist_network = Model.get('distribution.network')(dist_network.id)
    >>> contract.start_date = dt.date.today()
    >>> product = Model.get('offered.product')(product.id)
    >>> contract.product = product
    >>> contract.contract_number = '123456789'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> option = covered_element.options.new()
    >>> option.coverage = coverage
    >>> contract.save()
    >>> ProtocolCoverage = Model.get(
    ...     'third_party_manager.protocol-offered.option.description')
    >>> pc = ProtocolCoverage(coverage=option.coverage, protocol=protocol)
    >>> pc.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> IrModel = Model.get('ir.model')
    >>> BatchParameter = Model.get('batch.launcher.parameter')
    >>> almerys_batch, = IrModel.find([
    ...         ('model', '=', 'third_party_protocol.batch.almerys'),
    ...         ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = almerys_batch
    >>> launcher.form.treatment_date = dt.date.today() + dt.timedelta(days=1)
    >>> directory_param, = [p for p in launcher.form.parameters
    ...     if p.code == 'directory']
    >>> directory_param.value = temp_dir
    >>> launcher.form.parameters.append(
    ...     BatchParameter(code='filepath_template', value='%{BATCHNAME}/%{FILENAME}'))
    >>> launcher.execute('process')
    >>> len(list(batch_dir.glob('*.xml')))
    1
    >>> doc_file = next(batch_dir.glob('*.xml'))
    >>> xsd = file_open(
    ...     'third_party_protocol_almerys/NormeIntegrationMedline.2.8.17.xsd',
    ...     mode='rb')
    >>> with doc_file.open() as doc, xsd:
    ...     document = etree.parse(doc)
    ...     etree.XMLSchema(etree.parse(xsd)).assertValid(document)
    >>> ns = {'almerys': "http://www.almerys.com/NormeV3"}
    >>> document.xpath('//almerys:NOEMISE', namespaces=ns)[0].text
    'false'
    >>> len(document.xpath('//almerys:SERVICE_TP', namespaces=ns))
    1
    >>> document.xpath('//almerys:IBAN_BBAN', namespaces=ns)[0].text
    '1420041010050500013M026'
    >>> document.xpath('//almerys:REF_INTERNE_CG', namespaces=ns)[0].text
    'REF INTERNE'
    >>> AlmerysReturn = Model.get('return.almerys')

Constants::

    >>> contract_start_date = datetime.date(2014, 4, 10)

Create Contract::

    >>> Contract = Model.get('contract')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.contract_number = 'CT20190600019'
    >>> contract.save()
    >>> today = datetime.date.today()
    >>> module_file = almerys_batch_2.__file__
    >>> module_folder = os.path.dirname(module_file)
    >>> def debug_print(to_print):
    ...     print(to_print, file=sys.stderr)
    >>> def import_almerys_v3_return_handler(file_name):
    ...     debug_print('testing %s' % file_name)
    ...     IrModel = Model.get('ir.model')
    ...     almerys_return__batch, = IrModel.find([
    ...             ('model', '=', 'batch.almerys.feedback'),
    ...             ])
    ...     launcher = Wizard('batch.launcher')
    ...     launcher.form.batch = almerys_return__batch
    ...     dir_ = os.path.join(module_folder, 'tests_imports/')
    ...     file_path = dir_ + file_name
    ...     for i in range(0, len(launcher.form.parameters)):
    ...         if launcher.form.parameters[i].code == 'in_path':
    ...             launcher.form.parameters[i].value = file_path
    ...         elif launcher.form.parameters[i].code == 'archive_path':
    ...             launcher.form.parameters[i].value = dir_
    ...     try:
    ...         launcher.execute('process')
    ...         return
    ...     finally:
    ...         archive_path = dir_ + 'treated_%s_%s' % (str(today),
    ...             file_name)
    ...         cmd = 'mv %s %s' % (archive_path, file_path)
    ...         __ = popen(cmd.split())  # NOQA
    >>> __ = import_almerys_v3_return_handler('AlmerysReturnV3Flow.xml')  # NOQA
    >>> almerys_return_object = AlmerysReturn.find([
    ...         ('contract.contract_number', '=', 'CT20190600019'),
    ...         ('file_number', '=', '100005')])
    >>> len(almerys_return_object) == 4
    True
    >>> rec = almerys_return_object[0]
    >>> rec.error_code == 'ERR_V3_00000011'
    True
    >>> rec.error_label == 'Membre 2604 n\'a pas de NNI, mais lui/elle est relie au ' \
    ...                    'SERVICE_TP_PEC.'
    True
