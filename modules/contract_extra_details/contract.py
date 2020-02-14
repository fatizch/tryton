# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils
from trytond.modules.coog_core.extra_details import WithExtraDetails

__all__ = [
    'Contract',
    'ContractExtraDataRevision',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    current_extra_details = fields.Function(
        fields.Dict('extra_details.configuration.line', 'Current Details',
            states={'invisible': ~Eval('current_extra_details')}),
        'getter_current_extra_details')

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'update_extra_details')]

    def update_extra_details(self, date=None):
        if not self.product.extra_details_rule or not self.extra_datas:
            return
        Version = Pool().get('contract.extra_data')
        if date is None:
            date = utils.today()
        details = self._get_extra_details_at_date(date)
        if (self.extra_datas[-1].extra_details and
                self.extra_datas[-1].extra_details != details):
            new_version = Version(extra_details=details, date=date,
                extra_data_values=self.extra_datas[-1].extra_data_values)
            self.extra_datas = list(self.extra_datas) + [new_version]
        else:
            self.extra_datas[-1].extra_details = details
            self.extra_datas = list(self.extra_datas)
        self.save()

    def getter_current_extra_details(self, name):
        if not self.product.extra_details_rule:
            return
        return self._get_extra_details_at_date(max(self.start_date,
            utils.today()))

    def _get_extra_details_at_date(self, date):
        data = {'date': date}
        self.init_dict_for_rule_engine(data)
        return self.product.calculate_extra_details(data)

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls)._calculate_methods_after_endorsement() | {
            'update_extra_details_after_endorsement'}

    def update_extra_details_after_endorsement(self, caller=None):
        if not caller:
            return
        ContractEndorsement = Pool().get('endorsement.contract')
        if not isinstance(caller, ContractEndorsement):
            return
        self.update_extra_details(caller.endorsement.effective_date)


class ContractExtraDataRevision(WithExtraDetails, metaclass=PoolMeta):
    __name__ = 'contract.extra_data'

    @classmethod
    def __setup__(cls):
        super(ContractExtraDataRevision, cls).__setup__()
        cls.extra_details.readonly = True

    @classmethod
    def default_extra_details(cls):
        return {}
