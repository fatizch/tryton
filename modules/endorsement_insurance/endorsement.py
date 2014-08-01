from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import relation_mixin

__all__ = [
    'CoveredElement',
    'Endorsement',
    'EndorsementContract',
    'EndorsementCoveredElement',
    ]


class CoveredElement(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.covered_element'


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind == 'covered_element':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    covered_elements = fields.One2Many('endorsement.contract.covered_element',
        'contract_endorsement', 'Covered Elements', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'],
        context={'definition': Eval('definition')})

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        covered_element_summary = '\n'.join([covered_element.get_summary(
                    'contract.covered_element',
                    self.base_instance, indent=4)
                for covered_element in self.covered_elements])
        if covered_element_summary:
            result += '  Covered elements modifications :\n'
            result += covered_element_summary
        return result

    def _restore_history(self):
        contract, hcontract = super(EndorsementContract,
            self)._restore_history()
        covered_element_ids = set((covered_element.id for covered_element in (
                    contract.covered_elements +
                    hcontract.covered_elements)))
        Pool().get('contract.covered_element').restore_history(list(
                covered_element_ids), self.applied_on)
        return contract, hcontract

    @property
    def apply_values(self):
        values = super(EndorsementContract, self).apply_values
        covered_elements = []
        for covered_element in self.covered_elements:
            covered_elements.append(covered_element.apply_values)
        if covered_elements:
            values['covered_elements'] = covered_elements
        return values


class EndorsementCoveredElement(relation_mixin(
            'endorsement.contract.covered_element.field', 'covered_element',
            'contract.covered_element', 'Covered Elements'),
        model.CoopSQL, model.CoopView):
    'Endorsement Covered Element'

    __name__ = 'endorsement.contract.covered_element'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElement, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id
