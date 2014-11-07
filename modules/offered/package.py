from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'Package',
    'PackageOptionDescriptionRelation',
    'ProductPackageRelation',
    ]


class Package(model.CoopSQL, model.CoopView):
    'Package'

    __name__ = 'offered.package'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    options = fields.Many2Many('offered.package-option.description',
        'package', 'option', 'Options')

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


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
