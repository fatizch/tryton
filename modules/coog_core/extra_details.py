# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.cache import Cache
from trytond.model import Model, DictSchemaMixin, Unique
from trytond.model.fields.dict import TranslatedDict

import coog_string
import fields
import model


class WithExtraDetails(Model):
    '''
        This class adds a dedicated dict field to store configurable details.
        There is also a function field that displays a textual synthesis of the
        dict field contents.

        The various details are configured per model in the
        extra_details.configuration model.
    '''
    extra_details = fields.Dict('extra_details.configuration.line',
        'Extra Details')
    extra_summary = fields.Function(
        fields.Text('Extra Summary'),
        'get_extra_summary')

    @classmethod
    def default_extra_details(cls):
        return Pool().get(
            'extra_details.configuration').get_extra_details_fields(
            cls.__name__)

    @classmethod
    def get_extra_summary(cls, instances, name):
        configuration = Pool().get(
            'extra_details.configuration').get_model_configuration(
            cls.__name__)
        if configuration is None:
            return {x.id: '' for x in instances}
        return configuration.generate_summary(instances)


class ExtraDetailsConfiguration(model.CoogSQL, model.CoogView):
    'Extra Details Configuration'

    __name__ = 'extra_details.configuration'

    model_name = fields.Selection('get_detailed_models', 'Model Name')
    lines = fields.One2Many('extra_details.configuration.line',
        'configuration', 'Lines', delete_missing=True)

    _per_model_cache = Cache('get_model_configuration')
    _per_model_lines_cache = Cache('get_extra_details_fields')
    _translation_cache = Cache('_get_extra_details_summary_cache')

    @classmethod
    def __setup__(cls):
        super(ExtraDetailsConfiguration, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('model_uniq', Unique(t, t.model_name),
                'The model must be unique!'),
            ]

    @classmethod
    def create(cls, vlist):
        vals = super(ExtraDetailsConfiguration, cls).create(vlist)
        cls._per_model_cache.clear()
        cls._per_model_lines_cache.clear()
        return vals

    @classmethod
    def write(cls, *args):
        super(ExtraDetailsConfiguration, cls).write(*args)
        cls._per_model_cache.clear()
        cls._per_model_lines_cache.clear()

    @classmethod
    def delete(cls, instances):
        super(ExtraDetailsConfiguration, cls).delete(instances)
        cls._per_model_cache.clear()
        cls._per_model_lines_cache.clear()

    @classmethod
    def get_detailed_models(cls):
        vals = []
        for model_name, klass in Pool().iterobject():
            if issubclass(klass, WithExtraDetails):
                vals.append((model_name, model_name))
        return vals

    @classmethod
    def get_model_configuration(cls, model_name):
        instance_id = cls._per_model_cache.get(model_name, -1)
        if instance_id != -1:
            return cls(instance_id) if instance_id else None
        instance = cls.search([('model_name', '=', model_name)])
        if instance:
            value = instance[0].id
        else:
            value = None
        cls._per_model_cache.set(model_name, value)
        return instance[0] if value else None

    @classmethod
    def get_extra_details_fields(cls, model_name):
        value = cls._per_model_lines_cache.get(model_name, None)
        if value is not None:
            return value
        model_config = cls.search([('model_name', '=', model_name)])
        if model_config:
            value = {x.name: None for x in model_config[0].lines}
        else:
            value = {}
        cls._per_model_lines_cache.set(model_name, value)
        return value

    def generate_summary(self, instances, lang=None):
        '''
            Generates a textual summary of the extra details for the given
            instances. The code is copy / pasted from extra_data, maybe move it
            in coog_string ?
        '''
        cls = self.__class__
        var_name = 'extra_details'
        res = {}
        for instance in instances:
            vals = []
            for key, value in getattr(instance, var_name).iteritems():
                cached_value = cls._translation_cache.get((key, value), None)
                if cached_value is not None:
                    vals.append(cached_value)
                    continue
                translated_vals = TranslatedDict(name=var_name, type_='values')
                translated_keys = TranslatedDict(name=var_name, type_='keys')
                trans_vals = translated_vals.__get__(instance,
                    instance.__class__)
                trans_keys = translated_keys.__get__(instance,
                    instance.__class__)
                vals = []
                for k, v in getattr(instance, var_name).iteritems():
                    if type(v) == bool:
                        vals.append((trans_keys[k], coog_string.translate_bool(
                                    v, lang)))
                    else:
                        vals.append((trans_keys[k], trans_vals[k]))
                    cls._translation_cache.set((k, v), vals[-1])
                break
            res[instance.id] = '\n'.join(('%s : %s' % (x, y) for x, y in vals))
        return res


class ExtraDetailsConfigurationLine(DictSchemaMixin, model.CoogSQL,
        model.CoogView):
    'Extra Details Configuration Line'

    __name__ = 'extra_details.configuration.line'

    configuration = fields.Many2One('extra_details.configuration',
        'Configuration', select=True, required=True, ondelete='CASCADE')

    @classmethod
    def create(cls, vlist):
        configuration = Pool().get('extra_details.configuration')
        vals = super(ExtraDetailsConfigurationLine, cls).create(vlist)
        configuration._per_model_lines_cache.clear()
        return vals

    @classmethod
    def write(cls, *args):
        configuration = Pool().get('extra_details.configuration')
        super(ExtraDetailsConfigurationLine, cls).write(*args)
        configuration._per_model_lines_cache.clear()

    @classmethod
    def delete(cls, instances):
        configuration = Pool().get('extra_details.configuration')
        super(ExtraDetailsConfigurationLine, cls).delete(instances)
        configuration._per_model_lines_cache.clear()
