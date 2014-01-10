from trytond.pyson import If, Eval

from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'ContractService',
    ]


class ContractService(model.CoopView, model.CoopSQL):
    'Contract Service'

    __name__ = 'contract.service'

    status = fields.Selection([
            ('calculating', 'Calculating'),
            ('not_eligible', 'Not Eligible'),
            ('calculated', 'Calculated'),
            ('delivered', 'Delivered'),
            ], 'Status')
    contract = fields.Many2One('contract', 'Contract', ondelete='RESTRICT')
    subscribed_service = fields.Many2One(
        'contract.option', 'Coverage', ondelete='RESTRICT', domain=[
            If(~~Eval('contract'), ('contract', '=', Eval('contract', {})), ())
            ], depends=['contract'])
    func_error = fields.Many2One('functional_error', 'Error',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('func_error'),
            'readonly': True,
            })

    def get_rec_name(self, name=None):
        if self.subscribed_service:
            res = self.subscribed_service.get_rec_name(name)
        else:
            res = super(ContractService, self).get_rec_name(name)
        if self.status:
            res += ' [%s]' % coop_string.translate_value(self, 'status')
        return res

    @staticmethod
    def default_status():
        return 'calculating'

    def get_contract(self):
        return self.contract
