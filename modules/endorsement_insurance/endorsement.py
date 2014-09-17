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
    'EndorsementCoveredElementOption',
    ]


class CoveredElement(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.covered_element'


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind in ('covered_element', 'option'):
            return Pool().get('endorsement.contract')(endorsement=self,
                covered_elements=[])
        return super(Endorsement, self).new_endorsement(endorsement_part)

    def find_parts(self, endorsement_part):
        if endorsement_part.kind == 'covered_element':
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    covered_elements = fields.One2Many('endorsement.contract.covered_element',
        'contract_endorsement', 'Covered Elements', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'],
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'mes_covered_element_modifications':
                'Covered Elements Modification',
                })

    def _restore_history(self):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        Option = pool.get('contract.option')
        contract, hcontract = super(EndorsementContract,
            self)._restore_history()
        covered_element_ids = set((covered_element.id for covered_element in (
                    contract.covered_elements +
                    hcontract.covered_elements)))
        option_ids = set((option.id
                for covered_element in (contract.covered_elements +
                    hcontract.covered_elements)
                for option in covered_element.options))
        CoveredElement.restore_history(list(
                covered_element_ids), self.applied_on)
        Option.restore_history(list(option_ids), self.applied_on)

        return contract, hcontract

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        covered_element_summary = '\n'.join([x.get_summary(
                    'contract.covered_element', x.covered_element,
                    indent=4, increment=2)
                for x in self.covered_elements])
        if covered_element_summary:
            result += ' %s :\n' % self.raise_user_error(
                'mes_covered_element_modifications', raise_exception=False)
            result += covered_element_summary
            result += '\n\n'
        return result

    @property
    def apply_values(self):
        values = super(EndorsementContract, self).apply_values
        covered_elements = []
        for covered_element in self.covered_elements:
            covered_elements.append(covered_element.apply_values)
        if covered_elements:
            values['covered_elements'] = covered_elements
        return values

    @property
    def new_covered_elements(self):
        elems = set([x for x in self.contract.covered_elements])
        for elem in getattr(self, 'covered_elements', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.covered_element)
            else:
                elems.remove(elem.covered_element)
                elems.add(elem)
        return elems

    @property
    def updated_struct(self):
        struct = super(EndorsementContract, self).updated_struct
        CoveredElement = Pool().get('endorsement.contract.covered_element')
        struct['covered_elements'] = covered_elements = {}
        for covered_element in self.new_covered_elements:
            covered_elements[covered_element] = CoveredElement.updated_struct(
                covered_element)
        return struct


class EndorsementCoveredElement(relation_mixin(
            'endorsement.contract.covered_element.field', 'covered_element',
            'contract.covered_element', 'Covered Elements'),
        model.CoopSQL, model.CoopView):
    'Endorsement Covered Element'

    __name__ = 'endorsement.contract.covered_element'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    options = fields.One2Many('endorsement.contract.covered_element.option',
        'covered_element_endorsement', 'Options')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElement, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_covered_element': 'New Covered Element',
                'mes_option_modifications': 'Option Modification',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    def get_rec_name(self, name):
        if self.covered_element:
            return self.covered_element.rec_name
        return self.raise_user_error('new_covered_element',
            raise_exception=False)

    def get_summary(self, model, base_object=None, indent=0, increment=2):
        result = super(EndorsementCoveredElement, self).get_summary(model,
            base_object, indent, increment)
        if self.action == 'remove':
            return result
        option_summary = '\n'.join([x.get_summary(
                    'contract.option', x.option,
                    indent=indent + increment, increment=increment)
                for x in self.options])
        if option_summary:
            result += '%s%s :\n' % (' ' * indent, self.raise_user_error(
                    'mes_option_modifications', raise_exception=False))
            result += option_summary
            result += '\n\n'
        return result

    @property
    def apply_values(self):
        values = super(EndorsementCoveredElement, self).apply_values
        option_values = []
        for option in self.options:
            option_values.append(option.apply_values)
        if option_values:
            if self.action == 'add':
                values[1][0]['options'] = option_values
            elif self.action == 'update':
                values[2]['options'] = option_values
        return values

    @property
    def new_options(self):
        if self.action == 'remove':
            return []
        elif self.action == 'add':
            return list(self.options)
        else:
            elems = set([x for x in self.covered_element.options])
            for elem in self.options:
                if elem.action == 'add':
                    elems.add(elem)
                elif elem.action == 'remove':
                    elems.remove(elem.option)
                else:
                    elems.remove(elem.option)
                    elems.add(elem)
        return elems

    @classmethod
    def updated_struct(cls, element):
        EndorsementCoveredElementOption = Pool().get(
            'endorsement.contract.covered_element.option')
        return {'options': {
                x: EndorsementCoveredElementOption.updated_struct(x)
                for x in (element.new_options if isinstance(element, cls)
                    else element.options)}}


class EndorsementCoveredElementOption(relation_mixin(
            'endorsement.contract.option.field', 'option', 'contract.option',
            'Options'),
        model.CoopSQL, model.CoopView):
    'Endorsement Option'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option'

    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element Endorsement',
        required=True, select=True, ondelete='CASCADE')
    coverage = fields.Function(
        fields.Many2One('offered.option.description', 'Coverage'),
        'on_change_with_coverage')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementOption, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_coverage': 'New Coverage: %s',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    @fields.depends('values', 'option')
    def on_change_with_coverage(self, name=None):
        result = self.values.get('coverage', None)
        if result:
            return result
        if self.option:
            return self.option.coverage.id

    def get_definition(self, name):
        return self.covered_element_endorsement.definition.id

    def get_rec_name(self, name):
        if self.option:
            return self.option.rec_name
        return self.raise_user_error('new_coverage', (self.coverage.rec_name),
            raise_exception=False)

    @classmethod
    def updated_struct(cls, option):
        return {}
