# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'ExpenseKind',
    ]


class ExpenseKind(model.CoopSQL, model.CoopView):
    'Expense Kind'

    __name__ = 'expense.kind'

    kind = fields.Selection([
            ('medical', 'Medical'),
            ('expert', 'Expert'),
            ('judiciary', 'Judiciary'),
            ('other', 'Other'),
            ], 'Kind')
    kind_string = kind.translated('kind')
    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    short_name = fields.Char('Short Name')

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)
