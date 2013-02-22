#-*- coding:utf-8 -*-
import copy
from trytond.pool import PoolMeta
from trytond.pyson import Eval
__all__ = [
    'LifeClaimDeliveredService',
]


class LifeClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(LifeClaimDeliveredService, cls).__setup__()
        cls.subscribed_service = copy.copy(cls.subscribed_service)
        if not cls.subscribed_service.domain:
            cls.subscribed_service.domain = []
        #TODO : Claimant could be a different person than covered person
        domain = ('covered_data.covered_element.person', '=',
            Eval('_parent_loss', {}).get('_parent_claim', {}).get('claimant'))
        cls.subscribed_service.domain.append(domain)
