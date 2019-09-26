===============================
Document requests API by token
===============================

Imports::

    >>> import datetime
    >>> import base64
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.config import config as trytond_config
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.offered_insurance.tests.tools import init_insurance_product
    >>> from trytond.modules.contract.tests.tools import add_quote_number_generator
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.party_cog.tests.tools import create_party_person
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user
    >>> config = activate_modules(['contract_insurance_document_request',
    ...         'api'], cache_file_name='contract_insurance_document_request')
    >>> _ = create_country()
    >>> Module = Model.get('ir.module')
    >>> currency = get_currency(code='EUR')
    >>> _ = create_company(currency=currency)
    >>> company = get_company()
    >>> execute_test_case('authorizations_test_case')
    >>> Group = Model.get('res.group')
    >>> privy_group = Group(name='privy')
    >>> privy_group.save()
    >>> User = Model.get('res.user')
    >>> contract_user, = User.find([('login', '=', 'contract_user')])
    >>> contract_user_privy_id, = User.copy([contract_user], context=config.context)
    >>> contract_user_privy = User(contract_user_privy_id)
    >>> contract_user_privy.login = 'contract_user_privy'
    >>> contract_user_privy.save()
    >>> privy_group.users.append(contract_user_privy)
    >>> privy_group.save()
    >>> api_group = Group(name='api_group')
    >>> api_group.save()
    >>> api_user = User(name='api_user', login='api_user')
    >>> api_user.save()
    >>> api_group.users.append(api_user)
    >>> api_group.save()
    >>> product = init_insurance_product(user_context=False)
    >>> product = add_quote_number_generator(product)
    >>> product.save()
    >>> DocumentDescription = Model.get('document.description')
    >>> subscription_request = DocumentDescription()
    >>> subscription_request.code = 'subscription_request'
    >>> subscription_request.name = "Subscription Request"
    >>> subscription_request.groups.append(privy_group)
    >>> subscription_request.save()
    >>> _ = product.document_rules.new()
    >>> _ = product.document_rules[0].documents.new()
    >>> product.document_rules[0].documents[0].document = subscription_request
    >>> product.document_rules[0].documents[0].blocking = True
    >>> product.save()
    >>> IrModel = Model.get('ir.model')
    >>> ReportTemplate = Model.get('report.template')
    >>> request_line_model, = IrModel.find(['model', '=',
    ...         'document.request.line'])
    >>> ExtraData = Model.get('extra_data')
    >>> question_1 = ExtraData()
    >>> question_1.type_ = 'char'
    >>> question_1.kind = 'document_request'
    >>> question_1.string = 'How do you do?'
    >>> question_1.string = 'how_do_you_do_'
    >>> question_1.save()
    >>> report_template = ReportTemplate()
    >>> report_template.name = 'Test genshi'
    >>> report_template.code = 'test_genshi'
    >>> report_template.on_model = request_line_model
    >>> report_template.input_kind = 'flat_document'
    >>> report_template.format_for_internal_edm = 'original'
    >>> report_template.save()
    >>> version = report_template.versions.new()
    >>> Lang = Model.get('ir.lang')
    >>> version.language, = Lang.find([('code', '=', 'en')])
    >>> version.name = 'test'
    >>> report_template.save()
    >>> question_doc_desc = DocumentDescription()
    >>> question_doc_desc.code = 'questions'
    >>> question_doc_desc.name = 'Questions'
    >>> question_doc_desc.template = report_template
    >>> question_doc_desc.extra_data_def.append(ExtraData(question_1.id))
    >>> question_doc_desc.groups.append(Group(privy_group.id))
    >>> question_doc_desc.save()
    >>> _ = product.document_rules[0].documents.new()
    >>> product.document_rules[0].documents[1].document = question_doc_desc
    >>> product.document_rules[0].documents[1].blocking = True
    >>> product.save()
    >>> config = switch_user('contract_user')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> company = get_company()
    >>> product = Model.get('offered.product')(product.id)
    >>> item_description = ItemDescription.find(
    ...     [('kind', '=', 'person')])[0]
    >>> subscriber = create_party_person(name="DUPONT", first_name="MARTIN")
    >>> subscriber.code = '2579'
    >>> subscriber.save()
    >>> Contract = Model.get('contract')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = datetime.date(2019, 1, 1)
    >>> contract.product = product
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> contract.save()
    >>> Contract.calculate([contract.id], config._context)
    >>> contract.reload()
    >>> assert len(contract.document_request_lines) == 0
    >>> config = switch_user('contract_user_privy')
    >>> Contract = Model.get('contract')
    >>> contract = Contract(contract.id)
    >>> assert len(contract.document_request_lines) == 2
    >>> by_code = {x.document_desc.code: x for x in contract.document_request_lines}
    >>> config = switch_user('api_user')
    >>> Contract = Model.get('contract')
    >>> contract = Contract(contract.id)
    >>> assert len(contract.document_request_lines) == 0
    >>> trytond_config.add_section('document_api')
    >>> trytond_config.set('document_api', 'document_token_secret', 'secret')
    >>> trytond_config.set('document_api', 'document_token_expiration_minutes', 10)
    >>> Contract = Model.get('contract')
    >>> _ = Contract.generate_required_documents_tokens([contract.id], config._context)
    >>> token = contract.document_token
    >>> assert token is not None
    >>> APIParty = Model.get('api.party')
    >>> requests_description = APIParty.token_document_requests(
    ...     {'document_token': token}, {'_debug_server': True}, {})
    >>> assert len(requests_description['informed_consent']) == 0
    >>> assert len(requests_description['documents_to_fill']) == 1
    >>> assert len(requests_description['documents_to_upload']) == 1
    >>> file_data = base64.b64encode(b"hello").decode('utf8')
    >>> to_upload = {
    ...     'id': str(by_code['subscription_request'].id),
    ...     'document_token': token,
    ...     'filename':
    ...     'some_filename.txt',
    ...     'binary_data': file_data
    ...     }
    >>> _ = APIParty.token_upload_documents(to_upload, {'_debug_server': True},
    ...     config.context)
    >>> config = switch_user('contract_user_privy')
    >>> RequestLine = Model.get('document.request.line')
    >>> attachment = RequestLine(by_code['subscription_request'].id).attachment
    >>> assert attachment.status == 'waiting_validation'
    >>> assert attachment.data == b'hello'
    >>> config = switch_user('api_user')
    >>> answer_data = {
    ...     'document_token': token,
    ...     'id': by_code['questions'].id,
    ...     'answers': {'how_do_you_do_': 'Doing all right.'}
    ...     }
    >>> APIParty = Model.get('api.party')
    >>> _ = APIParty.token_submit_document_answers(answer_data,
    ...     {'_debug_server': True}, {})
    >>> config = switch_user('contract_user_privy')
    >>> RequestLine = Model.get('document.request.line')
    >>> answered = RequestLine(by_code['questions'].id)
    >>> assert answered.data_status == 'done'
    >>> assert answered.extra_data == {'how_do_you_do_': 'Doing all right.'}
