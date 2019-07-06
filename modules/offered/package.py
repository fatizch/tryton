# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from trytond.modules.coog_core import model, fields
from trytond.modules.offered.extra_data import with_extra_data

__all__ = [
    'Package',
    'PackageOptionDescriptionRelation',
    'ProductPackageRelation',
    ]


class Package(model.CodedMixin, model.CoogView, with_extra_data([
        'package', 'contract'])):
    'Package'

    __name__ = 'offered.package'
    _func_key = 'code'

    # this many2many is not removed for compatibility with old code.
    # However it must not be used anymore
    options = fields.Many2Many('offered.package-option.description',
        'package', 'option', 'Options')
    option_relations = fields.One2Many('offered.package-option.description',
        'package', 'Option Relations', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        cls._error_messages.update({
                'package_only_on_subscription': 'Subscribe by package is only '
                'available on quote',
                })

    @classmethod
    def _export_skips(cls):
        return super(Package, cls)._export_light() | {'options'}

    def clean_and_add_options(self, contract, options_to_update,
            is_contract_option):
        Option = Pool().get('contract.option')
        # Keep existing option
        new_options = [o for o in options_to_update
                if is_contract_option == o.coverage.is_contract_option() and
                o.coverage in [o.option for o in self.option_relations]]
        # Add new option
        for option_relation in self.option_relations:
            coverage = option_relation.option
            if (is_contract_option != coverage.is_contract_option() or
                    coverage in [o.coverage for o in options_to_update]):
                # option already managed
                continue
            option = Option.new_option_from_coverage(coverage,
                contract.product, contract.initial_start_date)
            new_options.append(option)
        # Remove unecessary option
        to_delete = [o for o in options_to_update if o not in new_options]
        Option.delete(to_delete)
        return new_options

    def update_contract_options(self, contract):
        contract.options = self.clean_and_add_options(
            contract, contract.options, True)
        return contract

    def update_contract_extra_datas(self, contract):
        for key, value in self.extra_data.items():
            contract.set_extra_data_value(key, value)
        return contract

    def update_option_extra_data(self, option):
        for coverage in self.option_relations:
            if option.coverage == coverage.option:
                for key, value in coverage.extra_data.items():
                    option.set_extra_data_value(key, value)
        return option

    def update_options_extra_datas(self, contract):
        options = []
        for option in contract.options:
            options.append(self.update_option_extra_data(option))
        contract.options = options
        return contract

    def apply_package_on_contract(self, contract):
        if contract.status != 'quote':
            self.raise_user_error('package_only_on_subscription')
        contract = self.update_contract_options(contract)
        contract = self.update_contract_extra_datas(contract)
        contract = self.update_options_extra_datas(contract)
        return contract


class PackageOptionDescriptionRelation(model.CoogSQL, model.CoogView,
        with_extra_data(['option'])):
    'Package - Option Description Relation'

    __name__ = 'offered.package-option.description'

    package = fields.Many2One('offered.package', 'Package', ondelete='CASCADE',
        required=True, select=True)
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT', required=True)

    @classmethod
    def _export_skips(cls):
        return super(PackageOptionDescriptionRelation, cls)._export_light(
            ) | {'option'}


class ProductPackageRelation(model.CoogSQL):
    'Product - Package Relation'

    __name__ = 'offered.product-package'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    package = fields.Many2One('offered.package', 'Package',
        ondelete='RESTRICT')
