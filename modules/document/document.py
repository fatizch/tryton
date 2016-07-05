# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique
from trytond.modules.cog_utils import fields, model, coop_string

__all__ = [
    'DocumentDescription',
    ]


class DocumentDescription(model.CoopSQL, model.CoopView):
    'Document Description'

    __name__ = 'document.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)

    @classmethod
    def __setup__(cls):
        super(DocumentDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_unique', Unique(t, t.code),
                'The document description code must be unique'),
        ]
        cls._order.insert(0, ('name', 'ASC'))

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)
