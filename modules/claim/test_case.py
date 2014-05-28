from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache


MODULE_NAME = 'claim'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    _get_event_desc_cache = Cache('get_event_desc')
    _get_document_desc_cache = Cache('get_document_desc')

    @classmethod
    def global_search_list(cls):
        result = super(TestCaseModel, cls).global_search_list()
        result.add('claim')
        return result

    @classmethod
    def create_document(cls, **kwargs):
        Document = Pool().get('document.description')
        return Document(**kwargs)

    @classmethod
    def document_desc_test_case(cls):
        pass

    @classmethod
    def get_document_desc(cls, code):
        result = cls._get_document_desc_cache.get(code)
        if result:
            return result
        result = Pool().get('document.description').search([
                ('code', '=', code)], limit=1)[0]
        cls._get_document_desc_cache.set(code, result)
        return result

    @classmethod
    def create_event_desc(cls, **kwargs):
        EventDesc = Pool().get('benefit.event.description')
        if 'company' not in kwargs:
            kwargs['company'] = cls.get_company()
        return EventDesc(**kwargs)

    @classmethod
    def event_desc_test_case(cls):
        pass

    @classmethod
    def get_event_desc(cls, code):
        result = cls._get_event_desc_cache.get(code)
        if result:
            return result
        result = Pool().get('benefit.event.description').search([
                ('code', '=', code),
                ('company', '=', cls.get_company())], limit=1)[0]
        cls._get_event_desc_cache.set(code, result)
        return result

    @classmethod
    def create_loss_desc(cls, **kwargs):
        LossDesc = Pool().get('benefit.loss.description')
        if 'company' not in kwargs:
            kwargs['company'] = cls.get_company()
        return LossDesc(**kwargs)

    @classmethod
    def loss_desc_test_case(cls):
        pass
