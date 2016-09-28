# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields
from trytond.modules.process_cog import ProcessFinder, ProcessStart


__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'ContractSubscribeFindProcess',
    'ContractSubscribe',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class ContractSubscribeFindProcess(ProcessStart):
    'ContractSubscribe Find Process'

    __name__ = 'contract.subscribe.find_process'

    effective_date = fields.Date('Effective Date', required=True)
    product = fields.Many2One('offered.product', 'Product', domain=[
            ['OR',
                [('end_date', '>=', Eval('effective_date'))],
                [('end_date', '=', None)],
                ],
            ['OR',
                [('start_date', '<=', Eval('effective_date'))],
                [('start_date', '=', None)],
                ]
            ], depends=['effective_date'], required=True)
    party = fields.Many2One('party.party', 'Party', states={'invisible': True})

    @classmethod
    def build_process_domain(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'subscription'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            ContractSubscribeFindProcess, cls).build_process_depends()
        result.append('product')
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'contract')])[0].id

    @staticmethod
    def default_party():
        if Transaction().context.get('active_model') == 'party.party':
            return Transaction().context.get('active_id', None)

    @fields.depends('effective_date', 'product')
    def on_change_with_good_process(self):
        return super(ContractSubscribeFindProcess,
            self).on_change_with_good_process()


class ContractSubscribe(ProcessFinder):
    'Contract Subscribe'

    __name__ = 'contract.subscribe'

    @classmethod
    def get_parameters_model(cls):
        return 'contract.subscribe.find_process'

    @classmethod
    def get_parameters_view(cls):
        return \
            'contract_insurance_process.contract_subscribe_find_process_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.init_from_product(process_param.product,
                process_param.effective_date)
            if process_param.party:
                obj.subscriber = process_param.party
        return res, errs

    def finalize_main_object(self, obj):
        document_reception = Transaction().context.get(
            'current_document_reception', None)
        if not document_reception:
            return
        document = Pool().get('document.reception')(document_reception)
        document.transfer(obj)
