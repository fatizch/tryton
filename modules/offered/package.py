# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique

from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'Package',
    'PackageOptionDescriptionRelation',
    'ProductPackageRelation',
    ]


class Package(model.CoopSQL, model.CoopView):
    'Package'

    __name__ = 'offered.package'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    options = fields.Many2Many('offered.package-option.description',
        'package', 'option', 'Options')

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @classmethod
    def _export_light(cls):
        return super(Package, cls)._export_light() | {'options'}

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class PackageOptionDescriptionRelation(model.CoopSQL):
    'Package - Option Description Relation'

    __name__ = 'offered.package-option.description'

    package = fields.Many2One('offered.package', 'Package', ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class ProductPackageRelation(model.CoopSQL):
    'Product - Package Relation'

    __name__ = 'offered.product-package'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    package = fields.Many2One('offered.package', 'Package',
        ondelete='RESTRICT')
