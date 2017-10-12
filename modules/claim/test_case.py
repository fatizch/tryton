# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache


MODULE_NAME = 'claim'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    _get_event_desc_cache = Cache('get_event_desc')
    _get_document_desc_cache = Cache('get_document_desc')

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

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        for user_read in ['consultation', 'financial', 'contract']:
            user_group_dict[user_read].append('claim.group_claim_read')
        for user_manage in ['claim', 'underwriting']:
            user_group_dict[user_manage].append('claim.group_claim_manage')
        return user_group_dict
