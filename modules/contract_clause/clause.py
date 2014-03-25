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
    kind = fields.Function(
        fields.Char('Kind'),
        'on_change_with_kind')

    @fields.depends('clause')
    def on_change_with_customized_text(self, name=None):
        if not self.clause:
            return True
        return self.clause.customizable

    @fields.depends('clause', 'contract')
    def on_change_with_kind(self, name=None):
        if not self.clause:
            return ''
        return self.clause.kind

    @fields.depends('clause', 'contract')
    def on_change_with_text(self):
        if not self.clause:
            return ''
        return self.clause.get_version_at_date(
            self.contract.appliable_conditions_date).content

    def get_rec_name(self, name):
        return self.clause.get_rec_name(name)
