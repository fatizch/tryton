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
    override_text = fields.Function(
        fields.Boolean('Override Text', on_change_with=['clause'],
            states={'invisible': True}),
        'on_change_with_override_text')
    text = fields.Text('Text', states={
            'readonly': ~Eval('override_text'),
            'invisible': True,
        })
    visual_text = fields.Function(
        fields.Text('Clause Text', on_change_with=[
                'text', 'clause', 'override_text', 'contract']),
        'on_change_with_visual_text')
    kind = fields.Function(
        fields.Char('Kind', on_change_with=['clause', 'contract']),
        'on_change_with_kind')

    def on_change_with_override_text(self, name=None):
        if not self.clause:
            return False
        return self.clause.may_be_overriden

    def on_change_with_visual_text(self, name=None):
        if not self.clause:
            return ''
        if self.override_text:
            return self.text
        return self.clause.get_version_at_date(
            self.contract.appliable_conditions_date).content

    def on_change_with_kind(self, name=None):
        if not self.clause:
            return ''
        return self.clause.kind
