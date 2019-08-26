# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend

from sql.conditionals import Coalesce
from sql import Null

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils

__all__ = [
    'Contract',

    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    dist_network = fields.Many2One('distribution.network',
        'Distributor',
        domain=[('company', '=', Eval('company'))],
        states={'readonly': Eval('status') != 'quote'},
        depends=['company', 'status'], ondelete='RESTRICT')
    com_product = fields.Function(
        fields.Many2One('distribution.commercial_product',
            'Commercial Product'),
        'get_com_product_id')

    @classmethod
    def __register__(cls, module):
        # Migrate from 2.0 : remove agency and use the dist_network
        contract_handler = backend.get('TableHandler')(cls, module)
        migrate = contract_handler.column_exist('agency')

        super(Contract, cls).__register__(module)

        if migrate:
            pool = Pool()
            agent = pool.get('commission.agent').__table__()
            network = pool.get('distribution.network').__table__()
            cursor = Transaction().connection.cursor()
            for table in [cls.__table__, cls.__table_history__]:
                to_update = table()
                contract = table()
                update_data = contract.join(
                    agent, 'LEFT OUTER', condition=agent.id == contract.agent
                    ).join(network, condition=agent.party == network.party
                    ).select(contract.id,
                    Coalesce(contract.agency, network.id).as_('network'))
                cursor.execute(*to_update.update(
                        columns=[to_update.dist_network],
                        values=[update_data.network],
                        from_=[update_data],
                        where=((update_data.id == to_update.id) &
                            (to_update.dist_network == Null))))
            contract_handler.drop_column('agency')

    def get_com_product_id(self, name):
        if not self.dist_network:
            return None
        com_products = utils.get_good_versions_at_date(self.dist_network,
            'all_com_products', self.appliable_conditions_date)
        com_product = [x for x in com_products if x.product == self.product]
        if com_product:
            return com_product[0].id

    def get_dist_network(self):
        return self.dist_network

    def init_contract(self, product, party, contract_dict=None):
        super(Contract, self).init_contract(product, party, contract_dict)
        if not contract_dict or 'dist_network' not in contract_dict:
            return
        DistributionNetwork = Pool().get('distribution.network')
        self.dist_network, = DistributionNetwork.search(
            [('code', '=', contract_dict['dist_network']['code'])], limit=1,
            order=[])

    @classmethod
    def _export_light(cls):
        return super(Contract, cls)._export_light() | set(['dist_network'])

    def check_existence_dist_network(self):
        if not getattr(self, 'dist_network', None):
            raise ValidationError(gettext(
                    'contract_distribution.msg_no_dist_network',
                    contract=self.rec_name))

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'check_existence_dist_network')]
