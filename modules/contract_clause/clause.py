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
        fields.Boolean('Override Text', states={'invisible': True}),
        'on_change_with_override_text')
    text = fields.Text('Text', states={
            'readonly': ~Eval('override_text'),
            'invisible': True,
            }, depends=['override_text'])
    visual_text = fields.Function(
        fields.Text('Clause Text'),
        'on_change_with_visual_text')
    kind = fields.Function(
        fields.Char('Kind'),
        'on_change_with_kind')

    @fields.depends('clause')
    def on_change_with_override_text(self, name=None):
        if not self.clause:
            return False
        return self.clause.may_be_overriden

    @fields.depends('text', 'clause', 'override_text', 'contract')
    def on_change_with_visual_text(self, name=None):
        if not self.clause:
            return ''
        if self.override_text:
            return self.text
        return self.clause.get_version_at_date(
            self.contract.appliable_conditions_date).content

    @fields.depends('clause', 'contract')
    def on_change_with_kind(self, name=None):
        if not self.clause:
            return ''
        return self.clause.kind

    def get_rec_name(self, name):
        return self.clause.get_rec_name(name)
