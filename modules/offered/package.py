# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields
from trytond.modules.offered.extra_data import with_extra_data

__all__ = [
    'Package',
    'PackageOptionDescriptionRelation',
    'ProductPackageRelation',
    ]


class Package(model.CodedMixin, model.CoogView, with_extra_data(['package'])):
    'Package'

    __name__ = 'offered.package'
    _func_key = 'code'

    options = fields.Many2Many('offered.package-option.description',
        'package', 'option', 'Options')

    @classmethod
    def _export_light(cls):
        return super(Package, cls)._export_light() | {'options'}


class PackageOptionDescriptionRelation(model.CoogSQL):
    'Package - Option Description Relation'

    __name__ = 'offered.package-option.description'

    package = fields.Many2One('offered.package', 'Package', ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class ProductPackageRelation(model.CoogSQL):
    'Product - Package Relation'

    __name__ = 'offered.product-package'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    package = fields.Many2One('offered.package', 'Package',
        ondelete='RESTRICT')
