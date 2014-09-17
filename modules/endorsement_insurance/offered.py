from trytond.pool import PoolMeta
from trytond.pyson import Eval, And

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin

__metaclass__ = PoolMeta

__all__ = [
    'EndorsementPart',
    'EndorsementCoveredElementField',
    ]


class EndorsementPart:
    __name__ = 'endorsement.part'

    covered_elements_fields = fields.One2Many(
        'endorsement.contract.covered_element.field', 'endorsement_part',
        'Covered Element Fields', states={
            'invisible': Eval('kind', '') != 'covered_element'},
        depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('covered_element', 'Covered Element'))
        cls.option_fields.states['invisible'] = And(
            cls.option_fields.states['invisible'],
            Eval('kind', '') != 'covered_element')

    def clean_up(self, endorsement):
        super(EndorsementPart, self).clean_up(endorsement)
        if (self.kind == 'covered_element' and self.covered_elements_fields
                and not self.option_fields):
            self.clean_up_relation(endorsement, 'covered_elements_fields',
                'covered_elements')


class EndorsementCoveredElementField(field_mixin('contract.covered_element'),
        model.CoopSQL, model.CoopView):
    'Endorsement Covered Element Field'

    __name__ = 'endorsement.contract.covered_element.field'
