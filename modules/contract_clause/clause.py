from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model

__all__ = [
    'ContractClause',
    ]


class ContractClause(model.CoopSQL, model.CoopView):
    'Contract Clause'

    __name__ = 'contract.clause'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', ondelete='RESTRICT')
    customized_text = fields.Function(
        fields.Boolean('Customized Text', states={'invisible': True}),
        'on_change_with_customized_text')
    text = fields.Text('Text', states={
            'readonly': ~Eval('customized_text'),
            }, depends=['customized_text'])

    @fields.depends('clause')
    def on_change_with_customized_text(self, name=None):
        return self.clause.customizable if self.clause else True

    @fields.depends('clause')
    def on_change_with_text(self):
        if not self.clause:
            return ''
        return self.clause.content

    def get_rec_name(self, name):
        return self.clause.rec_name if self.clause else self.text

    @staticmethod
    def default_customized_text():
        return True
