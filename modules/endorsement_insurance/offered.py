# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, And

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin

__metaclass__ = PoolMeta

__all__ = [
    'EndorsementPart',
    'EndorsementCoveredElementField',
    'EndorsementExtraPremiumField',
    'EndorsementCoveredElementVersionField',
    'EndorsementExclusionField',
    ]


class EndorsementPart:
    __name__ = 'endorsement.part'

    covered_elements_fields = fields.One2Many(
        'endorsement.contract.covered_element.field', 'endorsement_part',
        'Covered Element Fields', states={
            'invisible': Eval('kind', '') != 'covered_element'},
        depends=['kind'], delete_missing=True)
    extra_premium_fields = fields.One2Many(
        'endorsement.contract.extra_premium.field', 'endorsement_part',
        'Extra Premium Fields', states={
            'invisible': Eval('kind', '') != 'extra_premium'},
        depends=['kind'], delete_missing=True)
    exclusion_fields = fields.One2Many(
        'endorsement.contract.option.exclusion.field', 'endorsement_part',
        'Exclusion Fields', states={
            'invisible': Eval('kind', '') != 'option'},
        depends=['kind'], delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('covered_element', 'Covered Element'))
        cls.kind.selection.append(('extra_premium', 'Extra Premium'))
        cls.option_fields.states['invisible'] = And(
            cls.option_fields.states['invisible'],
            Eval('kind', '') != 'covered_element')

    def on_change_with_endorsed_model(self, name=None):
        if self.kind in ('covered_element', 'extra_premium'):
            return Pool().get('ir.model').search([
                    ('model', '=', 'contract')])[0].id
        return super(EndorsementPart, self).on_change_with_endorsed_model(name)

    def clean_up(self, endorsement):
        super(EndorsementPart, self).clean_up(endorsement)
        if (self.kind == 'covered_element' and self.covered_elements_fields
                and not self.option_fields):
            self.clean_up_relation(endorsement, 'covered_elements_fields',
                'covered_elements')
        if self.kind == 'extra_premium':
            to_delete = []
            for covered_element in endorsement.covered_elements:
                for option in covered_element.options:
                    extra_premiums = []
                    for extra_premium in option.extra_premiums:
                        if extra_premium.values:
                            for field in self.extra_premium_fields:
                                if field.name in extra_premium.values:
                                    del extra_premium.values[field.name]
                        if not extra_premium.values:
                            to_delete.append(extra_premium)
                        else:
                            extra_premiums.append(extra_premium)
                    option.extra_premiums = extra_premiums
            if to_delete:
                ExtraPremiumEndorsement = Pool().get(
                    'endorsement.contract.extra_premium')
                ExtraPremiumEndorsement.delete(to_delete)


class EndorsementCoveredElementField(field_mixin('contract.covered_element'),
        model.CoopSQL, model.CoopView):
    'Endorsement Covered Element Field'

    __name__ = 'endorsement.contract.covered_element.field'


class EndorsementCoveredElementVersionField(
        field_mixin('contract.covered_element.version'), model.CoopSQL,
        model.CoopView):
    'Endorsement Covered Element Version Field'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.version.field'


class EndorsementExtraPremiumField(field_mixin(
            'contract.option.extra_premium'), model.CoopSQL, model.CoopView):
    'Endorsement Extra Premium Field'

    __name__ = 'endorsement.contract.extra_premium.field'


class EndorsementExclusionField(field_mixin(
            'contract.option-exclusion.kind'), model.CoopSQL, model.CoopView):
    'Endorsement Exclusion Field'

    __name__ = 'endorsement.contract.option.exclusion.field'
