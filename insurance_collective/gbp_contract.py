#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.insurance_contract import Contract
from trytond.modules.coop_utils import utils

__all__ = [
        'GBPContract',
        ]


class GBPContract(Contract):
    'GBP Contract'
    #A GBP contract is slightly different from usual contract, as it does
    #not really have neither a product nor associated options.
    #
    #In fact, it defines a product, and as such shall not be mixed with
    #usual contracts.
    __name__ = 'ins_collective.gbp_contract'

    # GBP contract usually weigh a lot of money, so the subscribing society
    # usually have a dedicated contact for the insurance society on this
    # particular contract
    contact = fields.Many2One(
        'party.party',
        'Contact')

    # A GBP contract is a way for a society to provide health and life
    # coverage for its employees.
    # As such, it weighs a lot in terms of revenue, and the subscriber often
    # uses this as a way to negociate particular conditions (pricing for
    # instance), which made each gbp contract a unique offered product for the
    # employees.
    final_product = fields.One2Many('ins_collective.product', 'contract',
        'Final Product', size=1,
        states={'readonly': ~Eval('subscriber')},
        depends=['subscriber'])

    @classmethod
    def __setup__(cls):
        super(GBPContract, cls).__setup__()
        cls.subscriber = copy.copy(cls.subscriber)
        if not cls.subscriber.domain:
            cls.subscriber.domain = []
        cls.subscriber.domain.append(('is_society', '=', True))

    @classmethod
    def default_final_product(cls):
        return utils.create_inst_with_default_val(cls, 'final_product')

    def get_rec_name(self, name=None):
        if self.contract_number:
            return self.contract_number
        if self.final_product:
            return self.final_product[0].get_rec_name(name)
        return super(GBPContract, self).get_rec_name(name)

    @classmethod
    def get_offered_module_prefix(cls):
        return 'ins_collective'
