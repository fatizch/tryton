    >>> import datetime
    >>> import shutil
    >>> import os
    >>> import tempfile
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.party_cog.tests.tools import (
    ...     create_party_person, create_party_company)
    >>> in_directory = tempfile.TemporaryDirectory(prefix='claim_almerys_in')
    >>> indus_in_directory = tempfile.TemporaryDirectory(
    ...     prefix='claim_almerys_indus_in')
    >>> intermediary_directory = tempfile.TemporaryDirectory(
    ...     prefix='claim_almerys_in', suffix='statement')
    >>> out_directory = tempfile.TemporaryDirectory(prefix='claim_almerys_out')
    >>> indus_out_directory = tempfile.TemporaryDirectory(
    ...     prefix='claim_almerys_indus_out')
    >>> error_directory = tempfile.TemporaryDirectory(prefix='claim_almerys_error')
    >>> indus_error_directory = tempfile.TemporaryDirectory(
    ...     prefix='claim_almerys_indus_error')
    >>> _ = shutil.copy(
    ...     os.path.join(os.path.dirname(__file__), 'test_flow.xml'),
    ...     in_directory.name)
    >>> _ = shutil.copy(
    ...     os.path.join(os.path.dirname(__file__), 'test_indus.xml'),
    ...     indus_in_directory.name)
    >>> def check_error():
    ...     for name in os.listdir(error_directory.name):
    ...         with open(os.path.join(error_directory.name, name)) as fp:
    ...             print(fp.read())
    >>> config = activate_modules(['claim_almerys', 'batch_launcher'])
    >>> _ = create_country()
    >>> currency = get_currency(code='EUR')
    >>> _ = create_company(currency=currency)
    >>> company = get_company()
    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> Account = Model.get('account.account')
    >>> AccountType = Model.get('account.account.type')
    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> account_statement = Account(name="Almerys Statement")
    >>> account_type = AccountType(name="Statement", company=company)
    >>> account_type.save()
    >>> account_statement.type = account_type
    >>> account_statement.save()
    >>> Sequence = Model.get('ir.sequence')
    >>> Journal = Model.get('account.journal')
    >>> StatementJournal = Model.get('account.statement.journal')
    >>> statement_journal = StatementJournal(name="Almerys")
    >>> statement_journal.journal = Journal(name="Statement", type='statement')
    >>> statement_journal.journal.sequence, = Sequence.find(
    ...     [('code', '=', 'account.journal')])
    >>> statement_journal.journal.save()
    >>> statement_journal.validation = 'number_of_lines'
    >>> statement_journal.account = account_statement
    >>> statement_journal.process_method = 'other'
    >>> statement_journal.sequence = Sequence(name="Statement", code='statement')
    >>> statement_journal.sequence.save()
    >>> statement_journal.save()
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(
    ...     name="Payment", currency=currency, process_method='manual')
    >>> payment_journal.save()
    >>> Party = Model.get('party.party')
    >>> subscriber = create_party_person(name="DUPONT", first_name="MARTIN")
    >>> subscriber.code = '2579'
    >>> subscriber.save()
    >>> Insurer = Model.get('insurer')
    >>> insurer = Insurer()
    >>> insurer.party = create_party_company(name="Insurer")
    >>> insurer.party.save()
    >>> insurer.save()
    >>> ThirdPartyManager = Model.get('third_party_manager')
    >>> Protocol = Model.get('third_party_manager.protocol')
    >>> manager = ThirdPartyManager()
    >>> manager.party = create_party_company()
    >>> manager.save()
    >>> protocol = Protocol()
    >>> protocol.name = "Basic Protocol"
    >>> protocol.code = "BASIC"
    >>> protocol.technical_protocol = 'almerys'
    >>> protocol.almerys_ss_groupe = 'ss-groupe'
    >>> protocol.almerys_libelle_ss_groupe = 'SOUS-GROUPE'
    >>> protocol.almerys_support_tp = True
    >>> protocol.third_party_manager = manager
    >>> protocol.watched_events.extend(protocol.watched_events.find([
    ...             ('code', '=', 'activate_contract'),
    ...             ]))
    >>> protocol.save()
    >>> AlmerysConfig = Model.get('third_party_protocol.almerys.configuration')
    >>> almerys_config = AlmerysConfig(1)
    >>> almerys_config.invoiced_party = create_party_company(name="Almerys")
    >>> almerys_config.account_statement = account_statement
    >>> almerys_config.claim_journal = Journal(name="Claim", type='claim')
    >>> almerys_config.claim_journal.sequence = Sequence(
    ...     name="Claim", code='account.journal')
    >>> almerys_config.claim_journal.sequence.save()
    >>> almerys_config.claim_journal.save()
    >>> almerys_config.claim_statement_journal = statement_journal
    >>> almerys_config.save()
    >>> LossDescription = Model.get('benefit.loss.description')
    >>> tp_loss_description = LossDescription(code='TP', name='TP')
    >>> tp_loss_description.save()
    >>> htp_loss_description = LossDescription(code='HTP', name='HTP')
    >>> htp_loss_description.save()
    >>> EventDescription = Model.get('benefit.event.description')
    >>> tp_event_description = EventDescription(code='TP', name='TP')
    >>> tp_event_description.loss_descs.append(LossDescription(tp_loss_description.id))
    >>> tp_event_description.save()
    >>> htp_event_description = EventDescription(code='HTP', name='HTP')
    >>> htp_event_description.loss_descs.append(
    ...     LossDescription(htp_loss_description.id))
    >>> htp_event_description.save()
    >>> Product = Model.get('product.product')
    >>> Template = Model.get('product.template')
    >>> Uom = Model.get('product.uom')
    >>> Category = Model.get('product.category')
    >>> template = Template()
    >>> template.name = "Benefit Product"
    >>> template.type = 'service'
    >>> template.default_uom, = Uom.find([('name', '=', 'Unit')])
    >>> template.account_category = Category(
    ...     name="Account Category", accounting=True, code='account_category')
    >>> template.account_category.account_expense = accounts['expense']
    >>> template.account_category.account_revenue = accounts['revenue']
    >>> template.account_category.save()
    >>> template.products[0].code = 'benefit_product'
    >>> template.save()
    >>> account_product, = template.products
    >>> Benefit = Model.get('benefit')
    >>> benefit_tp = Benefit(
    ...     name="Benefit TP", code='TP_%s' % insurer.party.code, insurer=insurer,
    ...     delegation='prestation')
    >>> benefit_tp.loss_descs.append(LossDescription(tp_loss_description.id))
    >>> benefit_tp.start_date = datetime.date.min
    >>> benefit_tp.products.append(Product(account_product.id))
    >>> benefit_tp.save()
    >>> benefit_htp = Benefit(
    ...     name="Benefit HTP", code='HTP_%s' % insurer.party.code, insurer=insurer,
    ...     delegation='prestation_reimbursement')
    >>> benefit_htp.loss_descs.append(LossDescription(htp_loss_description.id))
    >>> benefit_htp.start_date = datetime.date.min
    >>> benefit_htp.products.append(Product(account_product.id))
    >>> benefit_htp.payment_journals.append(PaymentJournal(payment_journal.id))
    >>> benefit_htp.save()
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> contract_sequence_type = SequenceType(name="Contract", code='contract')
    >>> contract_sequence_type.save()
    >>> contract_sequence = Sequence(name="Contract", code='contract')
    >>> contract_sequence.save()
    >>> quote_sequence_type = SequenceType(name="Quote", code='quote')
    >>> quote_sequence_type.save()
    >>> quote_sequence = Sequence(name="Quote", code='quote')
    >>> quote_sequence.save()
    >>> ItemDescription = Model.get('offered.item.description')
    >>> item_description = ItemDescription(name="Test", code="TEST")
    >>> item_description.save()
    >>> OptionDescription = Model.get('offered.option.description')
    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = "Test Coverage"
    >>> coverage.code = "TEST"
    >>> coverage.start_date = datetime.date.min
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.almerys_management = True
    >>> coverage.account_for_billing = Account(accounts['revenue'].id)
    >>> coverage.third_party_protocols.append(Protocol(protocol.id))
    >>> coverage.save()
    >>> Product = Model.get('offered.product')
    >>> product = Product()
    >>> product.name = "Test Product"
    >>> product.code = "TEST"
    >>> product.company = company
    >>> product.currency = currency
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = datetime.date.min
    >>> product.coverages.append(OptionDescription(coverage.id))
    >>> product.save()
    >>> DistributionNetwork = Model.get('distribution.network')
    >>> dist_network = DistributionNetwork()
    >>> dist_network.name = "Distribution"
    >>> dist_network.party = create_party_company("I Distribute")
    >>> dist_network.save()
    >>> Contract = Model.get('contract')
    >>> contract = Contract(contract_number="CT{year}{month}00021")
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.dist_network = dist_network
    >>> contract.start_date = datetime.date(2019, 1, 1)
    >>> contract.product = product
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> TPPeriod = Model.get('contract.option.third_party_period')
    >>> third_party_period, = (
    ...     contract.covered_elements[0].options[0].third_party_periods)
    >>> third_party_period.save()
    >>> TPPeriod.write([third_party_period.id], {'status': 'sent'}, config.context)
    >>> IrModel = Model.get('ir.model')
    >>> BatchParameter = Model.get('batch.launcher.parameter')
    >>> batch, = IrModel.find([
    ...         ('model', '=', 'claim.almerys.claim_indemnification'),
    ...         ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> in_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'in_directory']
    >>> in_directory_param.value = in_directory.name
    >>> out_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'out_directory']
    >>> out_directory_param.value = intermediary_directory.name
    >>> error_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'error_directory']
    >>> error_directory_param.value = error_directory.name
    >>> launcher.execute('process')
    >>> check_error()
    >>> Claim = Model.get('claim')
    >>> len(Claim.find([]))
    2
    >>> Indemnification = Model.get('claim.indemnification')
    >>> indemnifications = Indemnification.find([])
    >>> len(indemnifications)
    2

 In xml file, we have a::


 (numFacture, numLigneFacture, mtRemboursementRC)::


 Equal to (3835428364, 1, 150.00) and (3835428364, 2, 15.00)::

    >>> expected_indemn_res = [
    ...     ('3835428364-1', Decimal('150.00'), 'paid'),
    ...     ('3835428364-2', Decimal('15.00'), 'paid')]
    >>> [(i.service.loss.code, i.amount, i.status) for i in indemnifications] == \
    ...     expected_indemn_res
    True
    >>> Invoice = Model.get('account.invoice')
    >>> invoices = Invoice.find([])
    >>> len(invoices)
    2

 In xml file, we have a total 165.00 invoice for claim 3835428364::


 due to third party statement and a total of 165.00 claim invoice::


 (150.00 + 15.00) due to claims indemnifications of claim::


 3835428364::

    >>> expected_inv_res = [
    ...     ('claim_invoice', Decimal('165.00')),
    ...     ('third_party_management', Decimal('165.00'))]
    >>> [(i.business_kind, i.total_amount) for i in invoices] == expected_inv_res
    True
    >>> sum(i.total_amount for i in invoices)
    Decimal('330.00')
    >>> batch, = IrModel.find([
    ...         ('model', '=', 'claim.almerys.statement_creation'),
    ...         ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> in_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'in_directory']
    >>> in_directory_param.value = intermediary_directory.name
    >>> out_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'out_directory']
    >>> out_directory_param.value = out_directory.name
    >>> error_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'error_directory']
    >>> error_directory_param.value = error_directory.name
    >>> launcher.execute('process')
    >>> check_error()
    >>> Statement = Model.get('account.statement')
    >>> statement, = Statement.find([])
    >>> len(statement.lines)
    1
    >>> batch, = IrModel.find([
    ...         ('model', '=', 'claim.almerys.payback_creation')])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> in_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'in_directory']
    >>> in_directory_param.value = indus_in_directory.name
    >>> out_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'out_directory']
    >>> out_directory_param.value = indus_out_directory.name
    >>> error_directory_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'error_directory']
    >>> error_directory_param.value = indus_error_directory.name
    >>> launcher.execute('process')
    >>> check_error()
    >>> Claim = Model.get('claim')
    >>> len(Claim.find([]))
    2
    >>> Indemnification = Model.get('claim.indemnification')
    >>> indemnifications = Indemnification.find([()])

 In test_indus.xml file we have a payback of 5.00 for loss::


 '3835428364-1' and of 4.00 for loss '3835428364-2'::


 Therefore old indemnifications of these claims will be::


 cancelled and new ones taking payback into account created::


 145.00 = 150.00 -5.00 and 11.00 = 15.00 - 4.00::

    >>> new_expected_indemn_res = [
    ...     ('3835428364-1', Decimal('145.00000'), 'paid'),
    ...     ('3835428364-1', Decimal('150.00'), 'cancel_paid'),
    ...     ('3835428364-2', Decimal('11.0000'), 'paid'),
    ...     ('3835428364-2', Decimal('15.00'), 'cancel_paid')]
    >>> non_cancelled_indemnifications = [i for i in indemnifications
    ...     if 'cancel' not in i.status]
    >>> len(non_cancelled_indemnifications)
    2
    >>> Invoice = Model.get('account.invoice')
    >>> invoices = Invoice.find([()])
    >>> new_expected_inv_res = [
    ...     ('claim_invoice', Decimal('-4.00'), 'posted'),
    ...     ('claim_invoice', Decimal('-5.00'), 'posted'),
    ...     ('claim_invoice', Decimal('165.00'), 'paid'),
    ...     ('third_party_management', Decimal('165.00'), 'posted')]

 Newly created invoices contain payback amounts::

    >>> [(i.business_kind, i.total_amount, i.state) for i in invoices] == \
    ...     new_expected_inv_res
    True
    >>> sum(i.total_amount for i in invoices)
    Decimal('321.00')
    >>> in_directory.cleanup()
    >>> out_directory.cleanup()
    >>> error_directory.cleanup()
    >>> intermediary_directory.cleanup()
    >>> indus_in_directory.cleanup()
    >>> indus_out_directory.cleanup()
    >>> indus_error_directory.cleanup()
