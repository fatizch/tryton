# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import If, Eval, Bool

from trytond.modules.coog_core import model, fields, coog_string

__all__ = [
    'ServiceMixin',
    'ContractService',
    ]


class ServiceMixin(model.CoogView):
    'Service Mixin'

    __name__ = 'contract.service_mixin'

    status = fields.Selection([
            ('calculating', 'Calculating'),
            ('not_eligible', 'Not Eligible'),
            ('calculated', 'Calculated'),
            ('delivered', 'Delivered'),
            ], 'Status')
    status_string = status.translated('status')
    contract = fields.Many2One('contract', 'Contract', ondelete='RESTRICT')
    option = fields.Many2One(
        'contract.option', 'Coverage', ondelete='RESTRICT', domain=[
            If(
                Bool(Eval('contract')),
                ('parent_contract', '=', Eval('contract', {})),
                ())
            ], depends=['contract'])
    func_error = fields.Many2One('functional_error', 'Error',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('func_error'),
            'readonly': True,
            })

    def get_rec_name(self, name=None):
        if self.option:
            res = self.option.get_rec_name(name)
        else:
            res = super(ServiceMixin, self).get_rec_name(name)
        if self.status:
            res += ' [%s]' % coog_string.translate_value(self, 'status')
        return res

    @staticmethod
    def default_status():
        return 'calculating'

    def get_contract(self):
        return self.contract

    def init_dict_for_rule_engine(self, cur_dict):
        self.option.init_dict_for_rule_engine(cur_dict)

    def calculate(self):
        raise NotImplementedError


class ContractService(ServiceMixin, model.CoogSQL):
    'Contract Service'

    __name__ = 'contract.service'
