# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.cog_utils import model, fields, coop_string, utils

__all__ = [
    'Tag',
    'TagObjectRelation',
    ]


class Tag(model.CoopSQL, model.CoopView):
    'Tag'

    __name__ = 'tag'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    parent = fields.Many2One('tag', 'Parent', ondelete='CASCADE', select=True)
    childs = fields.One2Many('tag', 'parent', 'Childs',
        target_not_required=True)
    tagged_objects = fields.One2Many('tag-object', 'tag', 'Tagged Objects',
        delete_missing=True)

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        result = super(Tag, cls)._export_skips()
        result.add('tagged_objects')
        return result

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class TagObjectRelation(model.CoopSQL, model.CoopView):
    'Relation tag to object'

    __name__ = 'tag-object'
    _rec_name = 'object_'

    tag = fields.Many2One('tag', 'Tag', ondelete='CASCADE', required=True,
        select=True)
    object_ = fields.Reference('Object', selection='models_get', required=True)

    @staticmethod
    def models_get():
        return utils.models_get()
