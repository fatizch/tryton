# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement import relation_mixin


__all__ = [
    'Beneficiary',
    'EndorsementContract',
    'EndorsementCoveredElementOption',
    'EndorsementBeneficiary',
    ]


class Beneficiary(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option.beneficiary'


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        option_idx = order.index('contract.option')
        order.insert(option_idx + 1, 'contract.option.beneficiary')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.covered_element'] += contract.covered_elements
            for covered_element in contract.covered_elements:
                instances['contract.option'] += \
                    covered_element.options
                for option in covered_element.options:
                    instances['contract.option.beneficiary'] += \
                        option.beneficiaries


class EndorsementCoveredElementOption:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option'

    beneficiaries = fields.One2Many('endorsement.contract.beneficiary',
        'covered_option_endorsement', 'Beneficiary Endorsement',
        delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementOption, cls).__setup__()
        cls._error_messages.update({
                'msg_beneficiary_modifications': 'Beneficiaries Modification',
                })

    def get_diff(self, model, base_object=None):
        result = super(EndorsementCoveredElementOption, self).get_diff(
            model, base_object)
        if self.action == 'remove':
            return result
        beneficiary_summary = [x.get_diff('contract.option.beneficiary',
                x.beneficiary) for x in self.beneficiaries]
        if beneficiary_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'msg_beneficiary_modifications',
                        raise_exception=False)),
                beneficiary_summary])
        return result

    def apply_values(self):
        values = super(EndorsementCoveredElementOption, self).apply_values()
        beneficiary_values = []
        for beneficiary in self.beneficiaries:
            beneficiary_values.append(beneficiary.apply_values())
        if beneficiary_values:
            if self.action == 'add':
                values[1][0]['beneficiaries'] = beneficiary_values
            elif self.action == 'update':
                values[2]['beneficiaries'] = beneficiary_values
        return values

    @property
    def new_beneficiaries(self):
        if self.action == 'remove':
            return []
        elif self.action == 'add':
            return list(self.beneficiaries)
        else:
            elems = set([x for x in self.option.beneficiaries])
            for elem in self.beneficiaries:
                if elem.action == 'add':
                    elems.add(elem)
                elif elem.action == 'remove':
                    elems.remove(elem.beneficiary)
                    elems.add(elem)
                else:
                    elems.remove(elem.beneficiary)
                    elems.add(elem)
        return elems

    @classmethod
    def updated_struct(cls, element):
        result = super(EndorsementCoveredElementOption, cls).updated_struct(
            element)
        EndorsementBeneficiary = Pool().get('endorsement.contract.beneficiary')
        result['beneficiaries'] = {
            x: EndorsementBeneficiary.updated_struct(x)
            for x in (element.new_beneficiaries
                if isinstance(element, cls)
                else element.beneficiaries)}
        return result


class EndorsementBeneficiary(relation_mixin(
            'endorsement.contract.beneficiary.field', 'beneficiary',
            'contract.option.beneficiary', 'Beneficiary'),
        model.CoogSQL, model.CoogView):
    'Endorsement Beneficiary'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.beneficiary'

    covered_option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option',
        'Extra Premium Endorsement', required=True, select=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementBeneficiary, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_beneficiary': 'New Beneficiary: %s',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.covered_option_endorsement.definition.id

    def get_rec_name(self, name):
        if self.extra_premium:
            return self.extra_premium.rec_name
        Beneficiary = Pool().get('contract.option.beneficiary')
        return self.raise_user_error('new_beneficiary',
            Beneficiary(**self.values).get_rec_name(None),
            raise_exception=False)

    @classmethod
    def updated_struct(cls, beneficiary):
        return {}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option'}
