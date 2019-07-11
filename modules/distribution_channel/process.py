# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields

__all__ = [
    'Process',
    'ProcessDistChannelRelation',
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
]


class Process(metaclass=PoolMeta):
    __name__ = 'process'

    for_channels = fields.Many2Many('process-distribution.channel',
        'process', 'dis_channel', 'Distribution Channels')


class ProcessDistChannelRelation(model.CoogSQL):
    'Process Product Relation'

    __name__ = 'process-distribution.channel'

    dis_channel = fields.Many2One(
        'distribution.channel', 'Distribution Channel', ondelete='CASCADE')
    process = fields.Many2One('process', 'Process', ondelete='CASCADE')


class ContractSubscribeFindProcess(metaclass=PoolMeta):
    __name__ = 'contract.subscribe.find_process'

    authorized_channels = fields.Many2Many(
        'distribution.channel', None, None, 'Authorized channels',
        states={'invisible': True})

    channel = fields.Many2One(
        'distribution.channel', 'Channel', required=True,
        domain=[('id', 'in', Eval('authorized_channels'))],
        depends=['authorized_channels']
    )

    @staticmethod
    def default_channel():
        return Pool().get('distribution.channel').search(
            ['code', '=', 'backoffice'])[0].id

    @fields.depends('product', 'distributor', 'authorized_commercial_products',
        'commercial_product', 'channel')
    def on_change_distributor(self):
        if self.distributor and self.channel:
            if self.channel.code not in [channel.code
                    for channel in self.distributor.all_net_channels]:
                self.channel = None
        self.simulate_init()

    @fields.depends(methods=['simulate_init'])
    def on_change_channel(self):
        self.simulate_init()

    @fields.depends('distributor', 'authorized_commercial_products',
        'commercial_product', 'channel')
    def on_change_commercial_product(self):
        super(ContractSubscribeFindProcess, self).on_change_commercial_product()

    @fields.depends('product', 'distributor', 'authorized_commercial_products',
        'commercial_product', 'channel')
    def simulate_init(self):
        res = super(ContractSubscribeFindProcess, self).simulate_init()
        if self.distributor:
            self.authorized_channels = [
                x.id for x in self.distributor.all_net_channels]
        if self.channel:
            if self.authorized_commercial_products:
                self.authorized_commercial_products = [
                    com_product for com_product in
                    self.authorized_commercial_products
                    if self.channel in com_product.dist_authorized_channels]
        return res

    @classmethod
    def build_process_domain(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_domain()
        result.append(['OR',
            ('for_channels', '=', None),
            ('for_channels', '=', Eval('channel'))])
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_depends()
        result.append('channel')
        return result

    @fields.depends('channel', 'commercial_product')
    def on_change_with_good_process(self):
        return super(ContractSubscribeFindProcess,
            self).on_change_with_good_process()


class ContractSubscribe(metaclass=PoolMeta):
    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.dist_channel = process_param.channel
        return res, errs
