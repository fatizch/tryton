# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import utils, fields
from trytond.modules.coog_core.extra_details import WithExtraDetails

__all__ = [
    'Contract',
    'ContractOption',
    'ContractOptionVersion',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def _calculate_methods(cls, product):
        methods = super(Contract, cls)._calculate_methods(product)
        result = []
        for method in methods:
            result.append(method)
            if method == ('contract', 'calculate_activation_dates'):
                result.append(('contract', 'compute_missing_options_details'))
        return result

    def compute_missing_options_details(self, date=None):
        for option in self._get_calculate_targets('options'):
            option.compute_missing_details(date)
        self.save()

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls)._calculate_methods_after_endorsement() | {
            'compute_endorsement_option_details'}

    def compute_endorsement_option_details(self, caller=None):
        if not caller:
            return
        pool = Pool()
        ContractEndorsement = pool.get('endorsement.contract')
        if not isinstance(caller, ContractEndorsement):
            return
        self.compute_missing_options_details(caller.endorsement.effective_date)


class ContractOption:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    current_extra_details = fields.Function(
        fields.Dict('extra_details.configuration.line', 'Current details',
            states={'invisible': ~Eval('current_extra_details')}),
        'getter_current_extra_details')

    def calculate_extra_details(self, date):
        assert date
        if not self.coverage.extra_details_rule:
            return
        data = {'date': date}
        self.init_dict_for_rule_engine(data)
        details = self.coverage.calculate_extra_details(data)
        version = self.get_version_at_date(date)
        if version.start != date:
            version = self.new_version_at_date(date)
        self.versions = list(self.versions)
        version.extra_details = details

    def getter_current_extra_details(self, name):
        if not self.coverage.extra_details_rule:
            return
        return self._get_extra_details_at_date(utils.today(), mode='current')

    def _get_extra_details_at_date(self, date, mode='normal'):
        data = {'date': date}
        self.init_dict_for_rule_engine(data)
        data['_extra_details_mode'] = mode
        return self.coverage.calculate_extra_details(data)

    def compute_missing_details(self, date=None):
        if not self.coverage.extra_details_rule:
            return
        data = {}
        for version in self.versions:
            version_date = version.start or self.start_date
            if version.extra_details and date and date > version_date:
                continue
            if not data:
                self.init_dict_for_rule_engine(data)
            data['date'] = version_date
            version.extra_details = self.coverage.calculate_extra_details(data)
        self.versions = self.versions


class ContractOptionVersion(WithExtraDetails):
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.version'

    @classmethod
    def __setup__(cls):
        super(ContractOptionVersion, cls).__setup__()
        cls.extra_details.readonly = True

    @classmethod
    def default_extra_details(cls):
        return {}
