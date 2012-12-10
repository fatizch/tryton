#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pool import Pool

from trytond.modules.coop_utils import model, utils


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
    rule = fields.Many2One('ins_product.clause_rule', 'Rule')

    @classmethod
    def version_model(cls):
        return 'ins_product.clause_version'

    @classmethod
    def default_versions(cls):
        return utils.create_inst_with_default_val(cls, 'versions')


class ClauseVersion(model.CoopSQL, model.VersionObject):
    'Clause Version'

    __name__ = 'ins_product.clause_version'

    content = fields.Text('Content')

    @classmethod
    def main_model(cls):
        return 'ins_product.clause'
