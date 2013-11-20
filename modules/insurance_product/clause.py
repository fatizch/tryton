#-*- coding:utf-8 -*-
from trytond.modules.coop_utils import model, utils, fields


__all__ = [
    'Clause',
    'ClauseVersion'
]


class Clause(model.CoopSQL, model.VersionedObject):
    'Clause'

    __name__ = 'ins_product.clause'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    title = fields.Char('Title')
    kind = fields.Selection('get_possible_clause_kinds', 'Kind')
    may_be_overriden = fields.Boolean('May be Overriden')

    @classmethod
    def version_model(cls):
        return 'ins_product.clause_version'

    @classmethod
    def default_versions(cls):
        return utils.create_inst_with_default_val(cls, 'versions')

    @classmethod
    def get_possible_clause_kinds(cls):
        return [
            ('', ''),
            ('beneficiary', 'Beneficiary'),
            ]


class ClauseVersion(model.CoopSQL, model.VersionObject):
    'Clause Version'

    __name__ = 'ins_product.clause_version'

    content = fields.Text('Content')

    @classmethod
    def main_model(cls):
        return 'ins_product.clause'
