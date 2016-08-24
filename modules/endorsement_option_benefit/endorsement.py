# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import relation_mixin, field_mixin


__all__ = [
    'EndorsementContract',
    'EndorsementPart',
    'EndorsementBenefitField',
    'EndorsementOptionBenefit',
    'EndorsementOptionVersion',
    ]


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        option_idx = order.index('contract.option.version')
        order.insert(option_idx + 1, 'contract.option.benefit')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(
            instances, at_date)
        for version in instances['contract.option.version']:
            instances['contract.option.benefit'] += version.benefits


class EndorsementOptionVersion:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option.version'

    benefits = fields.One2Many(
        'endorsement.contract.benefit',
        'option_version_endorsement',
        'Option Version Endorsement', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementOptionVersion, cls).__setup__()
        cls._error_messages.update({
               'msg_benefit_modifications': 'Benefit Modification'
                })

    def get_diff(self, model, base_object=None):
        result = super(
            EndorsementOptionVersion, self).get_diff(model, base_object)
        if self.action == 'remove':
            return result
        option_benefit_summary = [
            x.get_diff('contract.option.benefit', x.benefit)
            for x in self.benefits]

        if option_benefit_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'msg_benefit_modifications', raise_exception=False)),
                        option_benefit_summary])
        return result

    def apply_values(self):
        values = super(EndorsementOptionVersion, self).apply_values()
        option_benefit_values = []
        for option_benefit in self.benefits:
            option_benefit_values.append(option_benefit.apply_values())
        if option_benefit_values:
            if self.action == 'add':
                values[1][0]['benefits'] = option_benefit_values
            elif self.action == 'update':
                values[2]['benefits'] = option_benefit_values
        return values


class EndorsementOptionBenefit(relation_mixin(
            'endorsement.contract.benefit.field', 'benefit',
            'contract.option.benefit', 'Benefits'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option Benefit'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.benefit'

    option_version_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option.version',
        'Option Version Endorsement', required=True, select=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    indemnification_rule_extra_data = fields.Dict(
        'rule_engine.rule_parameter', 'Indemnification Extra Data')
    deductible_rule_extra_data = fields.Dict(
        'rule_engine.rule_parameter', 'Deductible Extra Data')

    @classmethod
    def __setup__(cls):
        super(EndorsementOptionBenefit, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_benefit': 'Benefit Endorsement: %s',
                })
        cls._endorsed_dicts = {
            'indemnification_rule_extra_data':
            'indemnification_rule_extra_data',
            'deductible_rule_extra_data': 'deductible_rule_extra_data'
            }

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.option_version_endorsement.definition.id

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'version'}


class EndorsementPart:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.part'

    benefit_fields = fields.One2Many(
        'endorsement.contract.benefit.field', 'endorsement_part',
        'Benefit Fields', states={
            'invisible': Eval('kind', '') != 'option'}, depends=['kind'],
        delete_missing=True)


class EndorsementBenefitField(field_mixin('contract.option.benefit'),
        model.CoopSQL, model.CoopView):
    'Endorsement Benefit Field'
    __name__ = 'endorsement.contract.benefit.field'
