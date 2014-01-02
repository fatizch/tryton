from trytond.modules.coop_utils import model, fields

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
    code = fields.Char('Code', required=True)
    name = fields.Char('Name')
    short_name = fields.Char('Short Name')
