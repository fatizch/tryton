# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'Loss',
    'Service',
    ]


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    main_services = fields.Function(
        fields.Many2Many('claim.service', None, None, 'Main services'),
        'getter_main_services', loader='loader_main_services')

    def getter_main_services(self, name):
        return [x.id for x in self.loader_main_services(name)]

    def loader_main_services(self, name):
        return [x for x in self.services if x.is_main_service]


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    sub_services = fields.Function(
        fields.Many2Many('claim.service', None, None, 'Sub services'),
        'getter_sub_services', loader='loader_sub_services')
    is_main_service = fields.Function(
        fields.Boolean('Is main service'),
        loader='loader_is_main_service')
    parent_service = fields.Function(
        fields.Many2One('claim.service', 'Parent service'),
        'getter_parent_service', loader='loader_parent_service')

    def loader_is_main_service(self, name):
        return not self.benefit.parent_benefits

    def getter_sub_services(self, name):
        return [x.id for x in self.loader_sub_services(name)]

    def loader_sub_services(self, name):
        return [x for x in self.loss.services
            if x.benefit in self.benefit.sub_benefits]

    def getter_parent_service(self, name):
        parent = self.loader_parent_service(name)
        return parent.id if parent else None

    def loader_parent_service(self, name):
        for service in self.loss.main_services:
            if service.benefit in self.benefit.parent_benefits:
                return service
