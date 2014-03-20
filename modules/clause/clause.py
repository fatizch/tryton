from trytond.modules.cog_utils import model, fields, coop_string


__all__ = [
    'Clause',
    'ClauseVersion',
    ]


class Clause(model.CoopSQL, model.VersionedObject):
    'Clause'

    __name__ = 'clause'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    title = fields.Char('Title')
    kind = fields.Selection([('', '')], 'Kind')
    customizable = fields.Boolean('Customizable')

    @classmethod
    def version_model(cls):
        return 'clause.version'

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def default_kind(cls):
        return ''

    def get_rec_name(self, name):
        return self.name


class ClauseVersion(model.CoopSQL, model.VersionObject):
    'Clause Version'

    __name__ = 'clause.version'

    content = fields.Text('Content')

    @classmethod
    def main_model(cls):
        return 'clause'
