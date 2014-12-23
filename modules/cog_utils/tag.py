from trytond.pool import Pool
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'Tag',
    'TagObjectRelation',
    ]


class Tag(model.CoopSQL, model.CoopView):
    'Tag'

    __name__ = 'tag'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    parent = fields.Many2One('tag', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('tag', 'parent', 'Childs')
    tagged_objects = fields.One2Many('tag-object', 'tag', 'Tagged Objects')

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
        return coop_string.remove_blank_and_invalid_char(self.name)


class TagObjectRelation(model.CoopSQL, model.CoopView):
    'Relation tag to object'

    __name__ = 'tag-object'
    _rec_name = 'object_'

    tag = fields.Many2One('tag', 'Tag', ondelete='CASCADE')
    object_ = fields.Reference('Object', selection='models_get')

    @staticmethod
    def models_get():
        pool = Pool()
        Model = pool.get('ir.model')
        models = Model.search([])
        res = []
        for cur_model in models:
            res.append([cur_model.model, cur_model.name])
        return res
