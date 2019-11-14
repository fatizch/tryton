# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
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
    def copy(cls, instances, default=None):
        default = default.copy() if default else {}
        default.setdefault('options', None)
        return super(Package, cls).copy(instances, default=default)

    @classmethod
    def _export_skips(cls):
        return super(Package, cls)._export_skips() | {'options'}

    def clean_and_add_options(self, contract, options_to_update,
            context, is_contract_option):
        Option = Pool().get('contract.option')
        args = {'date': contract.initial_start_date}
        context.init_dict_for_rule_engine(args)
        coverage_subscribable = [x.option for x in self.option_relations
            if x.option.get_subscription_behaviour(args)['behaviour'] !=
            'not_subscriptable']
        # Keep existing option
        new_options = [o for o in options_to_update
                if is_contract_option == o.coverage.is_contract_option() and
                o.coverage in coverage_subscribable]
        # Add new option
        for coverage in coverage_subscribable:
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
            contract, contract.options, contract, True)
        return contract

    @property
    def _contract_extra_data(self):
        ExtraData = Pool().get('extra_data')
        return {
            k: v for k, v in self.extra_data.items()
            if ExtraData._extra_data_struct(k)['kind'] == 'contract'
            }

    def update_contract_extra_datas(self, contract):
        for key, value in self._contract_extra_data.items():
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
            raise ValidationError(gettext(
                    'offered.msg_package_only_on_subscription'))
        contract = self.update_contract_options(contract)
        contract = self.update_contract_extra_datas(contract)
        contract = self.update_options_extra_datas(contract)
        return contract


class PackageOptionDescriptionRelation(model.ConfigurationMixin, model.CoogView,
        with_extra_data(['option'])):
    'Package - Option Description Relation'

    __name__ = 'offered.package-option.description'

    package = fields.Many2One('offered.package', 'Package', ondelete='CASCADE',
        required=True, select=True)
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT', required=True)

    @classmethod
    def _export_light(cls):
        return super(PackageOptionDescriptionRelation, cls)._export_light(
            ) | {'option'}


class ProductPackageRelation(model.ConfigurationMixin):
    'Product - Package Relation'

    __name__ = 'offered.product-package'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE')
    package = fields.Many2One('offered.package', 'Package',
        ondelete='RESTRICT')
