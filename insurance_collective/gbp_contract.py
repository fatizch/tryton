#-*- coding:utf-8 -*-
import copy

from trytond.model import fields

from trytond.modules.insurance_contract import GenericContract

__all__ = [
        'GBPContract',
        ]


class GBPContract(GenericContract):
    'GBP Contract'
    #A GBP contract is slightly different from usual contract, as it does
    #not really have neither a product nor associated options.
    #
    #In fact, it defines a product, and as such shall not be mixed with
    #usual contracts.
    __name__ = 'ins_collective.gbp_contract'

    # GBP contract usually weigh a lot of money, so the subscribing company
    # usually have a dedicated contact for the insurance company on this
    # particular contract
    contact = fields.Many2One(
        'party.party',
        'Contact')

    # A GBP contract is a way for a company to provide health and life
    # coverage for its employees.
    # As such, it weighs a lot in terms of revenue, and the subscriber often
    # uses this as a way to negociate particular conditions (pricing for
    # instance), which made each gbp contract a unique offered product for the
    # employees.
    final_product = fields.Many2One(
        'ins_collective.product',
        'Final Product')

    @classmethod
    def __setup__(cls):
        super(GBPContract, cls).__setup__()
        cls.subscriber = copy.copy(cls.subscriber)
        if not cls.subscriber.domain:
            cls.subscriber.domain = []
        cls.subscriber.domain.append(('is_company', '=', True))
