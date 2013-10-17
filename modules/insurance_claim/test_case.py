from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache


MODULE_NAME = 'insurance_claim'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    _get_event_desc_cache = Cache('get_event_desc')
    _get_document_desc_cache = Cache('get_document_desc')

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['document_desc_test_case'] = {
            'name': 'Document Desc Test Case',
            'dependencies': set([]),
        }
        result['event_desc_test_case'] = {
            'name': 'Event Desc Test Case',
            'dependencies': set([]),
        }
        result['loss_desc_test_case'] = {
            'name': 'Loss Desc Test Case',
            'dependencies': set(['document_desc_test_case',
                    'event_desc_test_case']),
        }
        return result

    @classmethod
    def global_search_list(cls):
        result = super(TestCaseModel, cls).global_search_list()
        result.add('ins_claim.claim')
        return result

    @classmethod
    def create_document(cls, code, name):
        Document = Pool().get('ins_product.document_desc')
        doc = Document()
        doc.code = code
        doc.name = name
        return doc

    @classmethod
    def document_desc_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        documents = []
        documents.append(cls.create_document('WI', translater(
                    'Work Incapacity')))
        documents.append(cls.create_document('DH', translater(
                    'Death Certificate')))
        documents.append(cls.create_document('AT', translater(
                    'Amortization Table')))
        documents.append(cls.create_document('DY', translater(
                    'Disability Justification')))
        return documents

    @classmethod
    def get_document_desc(cls, code):
        result = cls._get_document_desc_cache.get(code)
        if result:
            return result
        result = Pool().get('ins_product.document_desc').search([
                ('code', '=', code)], limit=1)[0]
        cls._get_document_desc_cache.set(code, result)
        return result

    @classmethod
    def create_event_desc(cls, code, name):
        EventDesc = Pool().get('ins_product.event_desc')
        event_desc = EventDesc()
        event_desc.code = code
        event_desc.name = name
        event_desc.company = cls.get_company()
        return event_desc

    @classmethod
    def event_desc_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        event_descs = []
        event_descs.append(cls.create_event_desc('DI', translater('Disease')))
        event_descs.append(cls.create_event_desc('AC', translater('Accident')))
        return event_descs

    @classmethod
    def get_event_desc(cls, code):
        result = cls._get_event_desc_cache.get(code)
        if result:
            return result
        result = Pool().get('ins_product.event_desc').search([
                ('code', '=', code),
                ('company', '=', cls.get_company())], limit=1)[0]
        cls._get_event_desc_cache.set(code, result)
        return result

    @classmethod
    def create_loss_desc(cls, code, name, item_kind, with_end_date,
            events, documents):
        LossDesc = Pool().get('ins_product.loss_desc')
        loss_desc = LossDesc()
        loss_desc.code = code
        loss_desc.name = name
        loss_desc.item_kind = item_kind
        loss_desc.with_end_date = with_end_date
        loss_desc.company = cls.get_company()
        loss_desc.event_descs = []
        loss_desc.documents = []
        for elem in events:
            loss_desc.event_descs.append(cls.get_event_desc(elem))
        for elem in documents:
            loss_desc.documents.append(cls.get_document_desc(elem))
        return loss_desc

    @classmethod
    def loss_desc_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        loss_descs = []
        loss_descs.append(cls.create_loss_desc('WI', translater(
                    'Work Incapacity'), 'person', True, ['AC'], ['WI']))
        loss_descs.append(cls.create_loss_desc('DH', translater('Death'),
                'person', False, ['AC', 'DI'], ['DH']))
        loss_descs.append(cls.create_loss_desc('DY', translater('Disability'),
                'person', False, ['AC', 'DI'], ['WI']))
        return loss_descs
