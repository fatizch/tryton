from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'ContractSubscribe',
    'ContractSubscribeFindProcess',
    ]


class ContractSubscribeFindProcess:
    'Contract Subscribe Find Process'

    __name__ = 'contract.subscribe.find_process'

    @classmethod
    def __setup__(cls):
        super(ContractSubscribeFindProcess, cls).__setup__()
        cls.product.domain = [
            'AND',
            cls.product.domain,
            [('is_group', '=', False)]]


class ContractSubscribe:
    'Contract Subscribe'

    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, obj, process_param):
        res, err = super(
            ContractSubscribe, self).init_main_object_from_process(
            obj, process_param)
        if res:
            obj.is_group = False
        return res, err
