# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column
from sql.conditionals import Coalesce
from sql.aggregate import Max

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement.endorsement import relation_mixin

__all__ = [
    'ContractOptionVersion',
    'CoveredElement',
    'CoveredElementVersion',
    'ExtraPremium',
    'OptionExclusionRelation',
    'Endorsement',
    'EndorsementContract',
    'EndorsementCoveredElement',
    'EndorsementCoveredElementVersion',
    'EndorsementCoveredElementOption',
    'EndorsementCoveredElementOptionVersion',
    'EndorsementExtraPremium',
    'EndorsementExclusion',
    ]


class ContractOptionVersion(object):
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.version'

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Option = pool.get('contract.option')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        option = Option.__table_history__()
        version = cls.__table_history__()

        super(ContractOptionVersion, cls).__register__(module)

        # Migration from 1.4 : Move contract.option->extra_data in
        # contract.option.version->extra_data
        option_h = TableHandler(Option, module, history=True)
        if option_h.column_exist('extra_data'):
            update_data = option.select(Column(option, '__id'),
                Coalesce(option.extra_data, '{}').as_('extra_data'))
            cursor.execute(*version.update(
                    columns=[version.extra_data],
                    values=[update_data.extra_data],
                    from_=[update_data],
                    where=Column(update_data, '__id') == Column(
                        version, '__id')))
            option_h.drop_column('extra_data')


class CoveredElement(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.covered_element'


class CoveredElementVersion(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.covered_element.version'

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        TableHandler = backend.get('TableHandler')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        covered_element_hist = CoveredElement.__table_history__()
        version_hist = cls.__table_history__()

        # Migration from 1.4 : Create default contract.covered_element.version
        covered_h = TableHandler(CoveredElement, module, history=True)
        to_migrate = covered_h.column_exist('extra_data')
        super(CoveredElementVersion, cls).__register__(module)

        if to_migrate:
            version_h = TableHandler(cls, module, history=True)
            # Delete previously created history, to have full control
            cursor.execute(*version_hist.delete())
            cursor.execute(*version_hist.insert(
                    columns=[
                        version_hist.create_date, version_hist.create_uid,
                        version_hist.write_date, version_hist.write_uid,
                        version_hist.extra_data, version_hist.covered_element,
                        version_hist.id, Column(version_hist, '__id')],
                    values=covered_element_hist.select(
                        covered_element_hist.create_date,
                        covered_element_hist.create_uid,
                        covered_element_hist.write_date,
                        covered_element_hist.write_uid,
                        covered_element_hist.extra_data,
                        covered_element_hist.id.as_('covered_element'),
                        covered_element_hist.id.as_('id'),
                        Column(covered_element_hist, '__id').as_('__id'))))
            cursor.execute(*version_hist.select(
                    Max(Column(version_hist, '__id'))))
            transaction.database.setnextid(transaction.connection,
                version_h.table_name + '__', cursor.fetchone()[0] or 0 + 1)
            covered_history_h = TableHandler(CoveredElement, module,
                history=True)
            covered_history_h.drop_column('extra_data')


class ExtraPremium(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option.extra_premium'


class OptionExclusionRelation(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.option-exclusion.kind'


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind in ('covered_element', 'option',
                'extra_premium'):
            return Pool().get('endorsement.contract')(endorsement=self,
                covered_elements=[])
        return super(Endorsement, self).new_endorsement(endorsement_part)

    def find_parts(self, endorsement_part):
        if endorsement_part.kind in ('covered_element', 'extra_premium'):
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    covered_elements = fields.One2Many('endorsement.contract.covered_element',
        'contract_endorsement', 'Covered Elements', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'mes_covered_element_modifications':
                'Covered Elements Modification',
                })

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.covered_element')
        order.insert(contract_idx + 2, 'contract.covered_element.version')
        option_idx = order.index('contract.option')
        order.insert(option_idx + 1, 'contract.option-exclusion.kind')
        order.insert(option_idx + 1, 'contract.option.extra_premium')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.covered_element'] += contract.covered_elements
            for covered_element in contract.covered_elements:
                instances['contract.covered_element.version'] += \
                    covered_element.versions
                instances['contract.option'] += covered_element.options
                for option in covered_element.options:
                    instances['contract.option.version'] += option.versions
        for option in instances['contract.option']:
            instances['contract.option-exclusion.kind'] += \
                option.exclusion_list
            instances['contract.option.extra_premium'] += option.extra_premiums

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        covered_element_summary = [x.get_diff('contract.covered_element',
                x.covered_element) for x in self.covered_elements]
        if covered_element_summary:
            result[1].append(['%s :' % self.raise_user_error(
                            'mes_covered_element_modifications',
                            raise_exception=False),
                    covered_element_summary])
        return result

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        covered_elements = []
        for covered_element in self.covered_elements:
            covered_elements.append(covered_element.apply_values())
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
        model.CoogSQL, model.CoogView):
    'Endorsement Covered Element'

    __name__ = 'endorsement.contract.covered_element'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Endorsement', required=True, select=True, ondelete='CASCADE')
    versions = fields.One2Many('endorsement.contract.covered_element.version',
        'covered_element_endorsement', 'Versions', delete_missing=True)
    options = fields.One2Many('endorsement.contract.covered_element.option',
        'covered_element_endorsement', 'Options', delete_missing=True)
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        '')
    name = fields.Function(
        fields.Char('Name'),
        '')
    item_desc = fields.Function(
        fields.Many2One('offered.item.description', 'Item Description'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElement, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_covered_element': 'New Covered Element',
                'mes_option_modifications': 'Option Modification',
                'mes_version_modifications': 'Version Modification',
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

    def get_diff(self, model, base_object=None):
        result = super(EndorsementCoveredElement, self).get_diff(model,
            base_object)
        if self.action == 'remove':
            return result
        version_summary = [x.get_diff('contract.covered_element.version',
                x.version)
            for x in self.versions]
        if version_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'mes_version_modifications',
                        raise_exception=False)),
                version_summary])
        option_summary = [x.get_diff('contract.option', x.option)
            for x in self.options]
        if option_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'mes_option_modifications',
                        raise_exception=False)),
                option_summary])
        return result

    def apply_values(self):
        values = super(EndorsementCoveredElement, self).apply_values()
        version_values = []
        for version in self.versions:
            version_values.append(version.apply_values())
        if version_values:
            if self.action == 'add':
                values[1][0]['versions'] = version_values
            elif self.action == 'update':
                values[2]['versions'] = version_values
        option_values = []
        for option in self.options:
            option_values.append(option.apply_values())
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

    def get_name_for_summary(self, field_, instance_id):
        pool = Pool()
        Date = pool.get('ir.date')
        Party = pool.get('party.party')
        CoveredElement = pool.get('contract.covered_element')
        lang = pool.get('res.user')(Transaction().user).language
        if field_.name != 'party':
            return super(EndorsementCoveredElement,
                self).get_name_for_summary(field_, instance_id)
        party = Party(instance_id)
        birth_date_str = Date.date_as_string(party.birth_date, lang)
        tmp_values = dict(self.values)
        tmp_values.update({'contract': self.contract_endorsement.contract})
        cov_rec_name = CoveredElement(**tmp_values).get_rec_name(None)
        return ', '.join([cov_rec_name, birth_date_str])

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'options', 'contract'}


class EndorsementCoveredElementVersion(relation_mixin(
            'endorsement.contract.covered_element.version.field', 'version',
            'contract.covered_element.version', 'Versions'),
        model.CoogSQL, model.CoogView):
    'Endorsement Covered Element Version'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.version'

    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Endorsement', required=True,
        select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    extra_data = fields.Dict('extra_data', 'Extra Data')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementVersion, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_covered_element_version': 'New Covered Element Version',
                })
        cls._endorsed_dicts = {'extra_data': 'extra_data'}

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.covered_element_endorsement.definition.id

    def get_rec_name(self, name):
        return '%s' % (self.raise_user_error('new_covered_element_version',
                raise_exception=False))

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'covered_element'}


class EndorsementCoveredElementOption(relation_mixin(
            'endorsement.contract.option.field', 'option', 'contract.option',
            'Options'),
        model.CoogSQL, model.CoogView):
    'Endorsement Option'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option'

    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element Endorsement',
        required=True, select=True, ondelete='CASCADE')
    versions = fields.One2Many(
        'endorsement.contract.covered_element.option.version',
        'option_endorsement', 'Versions Endorsements', delete_missing=True)
    extra_premiums = fields.One2Many('endorsement.contract.extra_premium',
        'covered_option_endorsement', 'Extra Premium Endorsement',
        delete_missing=True)
    exclusion_list = fields.One2Many('endorsement.contract.option.exclusion',
        'covered_option_endorsement', 'Exclusion Endorsements',
        delete_missing=True)
    coverage = fields.Function(
        fields.Many2One('offered.option.description', 'Coverage'),
        'on_change_with_coverage')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    manual_start_date = fields.Function(
        fields.Date('Start Date'),
        '')
    manual_end_date = fields.Function(
        fields.Date('End Date'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementOption, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_coverage': 'New Coverage: %s',
                'mes_versions_modification': 'Versions Modifications',
                'mes_extra_premium_modifications':
                'Extra Premium Modification',
                'mes_exclusion_modifications':
                'Exclusion Modifications',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    @fields.depends('values', 'option')
    def on_change_with_coverage(self, name=None):
        result = self.values.get('coverage', None) if self.values else None
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

    def get_diff(self, model, base_object=None):
        result = super(EndorsementCoveredElementOption, self).get_diff(
            model, base_object)
        if self.action == 'remove':
            return result
        option_summary = [x.get_diff('contract.option.version', x.version)
            for x in self.versions]
        if option_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'mes_option_modifications',
                        raise_exception=False)),
                option_summary])
        extra_premium_summary = [x.get_diff('contract.option.extra_premium',
                x.extra_premium) for x in self.extra_premiums]
        if extra_premium_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'mes_extra_premium_modifications',
                        raise_exception=False)),
                extra_premium_summary])
        exclusion_summary = [x.get_diff('contract.option-exclusion.kind',
                x.option_exclusion)
            for x in self.exclusion_list]
        if exclusion_summary:
            result[1].append(['%s :' % (self.raise_user_error(
                        'mes_exclusion_modifications',
                        raise_exception=False)),
                exclusion_summary])
        return result

    def apply_values(self):
        values = super(EndorsementCoveredElementOption, self).apply_values()
        version_values, extra_premium_values, exclusion_values = [], [], []
        for version in self.versions:
            version_values.append(version.apply_values())
        if version_values:
            if self.action == 'add':
                values[1][0]['versions'] = version_values
            elif self.action == 'update':
                values[2]['versions'] = version_values
        for extra_premium in self.extra_premiums:
            extra_premium_values.append(extra_premium.apply_values())
        if extra_premium_values:
            if self.action == 'add':
                values[1][0]['extra_premiums'] = extra_premium_values
            elif self.action == 'update':
                values[2]['extra_premiums'] = extra_premium_values
        for exclusion in self.exclusion_list:
            exclusion_values.append(exclusion.apply_values())
        if exclusion_values:
            if self.action == 'add':
                values[1][0]['exclusion_list'] = exclusion_values
            elif self.action == 'update':
                values[2]['exclusion_list'] = exclusion_values
        return values

    @property
    def new_extra_premiums(self):
        if self.action == 'remove':
            return []
        elif self.action == 'add':
            return list(self.extra_premiums)
        else:
            elems = set([x for x in self.option.extra_premiums])
            for elem in self.extra_premiums:
                if elem.action == 'add':
                    elems.add(elem)
                elif elem.action == 'remove':
                    elems.remove(elem.extra_premium)
                    elems.add(elem)
                else:
                    elems.remove(elem.extra_premium)
                    elems.add(elem)
        return elems

    @classmethod
    def updated_struct(cls, element):
        EndorsementExtraPremium = Pool().get(
            'endorsement.contract.extra_premium')
        return {'extra_premiums': {
                x: EndorsementExtraPremium.updated_struct(x)
                for x in (element.new_extra_premiums
                    if isinstance(element, cls)
                    else element.extra_premiums)}}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'covered_element', 'contract'}

    @classmethod
    def _auto_update_ignore_fields(cls):
        return {'current_extra_data'}


class EndorsementCoveredElementOptionVersion(relation_mixin(
            'endorsement.contract.option.version.field', 'version',
            'contract.option.version', 'Versions'),
        model.CoogSQL, model.CoogView):
    'Endorsement Option Version'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option.version'

    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Endorsement',
        required=True, select=True, ondelete='CASCADE')
    extra_data = fields.Dict('extra_data', 'Extra Data')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementOptionVersion, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_option_version': 'New Option Version',
                })
        cls._endorsed_dicts = {'extra_data': 'extra_data'}

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.option_definition.definition.id

    def get_rec_name(self, name):
        return '%s' % (self.raise_user_error('new_option_version',
                raise_exception=False))

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option'}


class EndorsementExtraPremium(relation_mixin(
            'endorsement.contract.extra_premium.field', 'extra_premium',
            'contract.option.extra_premium', 'Extra Premiums'),
        model.CoogSQL, model.CoogView):
    'Endorsement Extra Premium'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.extra_premium'

    covered_option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option',
        'Extra Premium Endorsement', required=True, select=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementExtraPremium, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_extra_premium': 'New Extra Premium: %s',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.covered_option_endorsement.definition.id

    def get_rec_name(self, name):
        if self.extra_premium:
            return self.extra_premium.rec_name
        ExtraPremium = Pool().get('contract.option.extra_premium')
        return self.raise_user_error('new_extra_premium',
            ExtraPremium(**self.values).get_rec_name(None),
            raise_exception=False)

    @classmethod
    def updated_struct(cls, option):
        return {}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option', 'contract_status', 'start_date'}


class EndorsementExclusion(relation_mixin(
            'endorsement.contract.option.exclusion.field', 'option_exclusion',
            'contract.option-exclusion.kind', 'Exclusion'),
        model.CoogSQL, model.CoogView):
    'Endorsement Exclusion'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.option.exclusion'

    covered_option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option',
        'Option Endorsement', required=True, select=True,
        ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    exclusion = fields.Function(
        fields.Many2One('offered.exclusion', 'Exclusion'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementExclusion, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']
        cls._error_messages.update({
                'new_exclusion': 'New Exclusion: %s',
                })

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.covered_option_endorsement.definition.id

    def get_rec_name(self, name):
        return self.exclusion.rec_name if self.exclusion else ''

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option'}
