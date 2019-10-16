# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pyson import Eval

from trytond.pool import Pool
from trytond.model import Unique

from trytond.modules.coog_core import model, fields
from trytond.ir.resource import ResourceMixin

__all__ = [
    'WebUIResource',
    'WebUIResourceKey',
    'WebUIResourceMixin',
    'RelationWebUIResourceKeyIRModel',
    ]


class WebUIResource(model.CoogSQL, model.CoogView):
    'Web UI Resource'
    __name__ = 'web.ui.resource'

    origin_resource = fields.Reference('Origin', 'select_resource_models',
        required=True, help='The record to which this resource will be linked')
    key = fields.Many2One('web.ui.resource.key', 'Key', required=True,
        ondelete='RESTRICT', help='Link to the description of this resource'
            ' for this origin',
        domain=[('ir_model_resource_key', '=', Eval('ir_model_resource'))],
        depends=['ir_model_resource'])
    value = fields.Text('Value', help='The value for this origin / key pair')
    ir_model_resource = fields.Function(
        fields.Many2One('ir.model', 'IR Model Resource Key',
            states={'invisible': True}), 'on_change_with_ir_model_resource')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('key_origin_unique', Unique(t, t.origin_resource, t.key),
                'The origin / key pair must be unique')]

    @classmethod
    def __register__(cls, module_name):
        super(WebUIResource, cls).__register__(module_name)
        # Migration from 2.4 Drop api.resource
        TableHandler = backend.get('TableHandler')
        if TableHandler.table_exist('api_resource'):
            TableHandler.drop_table('api.resource', 'api_resource')

    @fields.depends('origin_resource')
    def on_change_with_ir_model_resource(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        if self.origin_resource:
            return Model.search([
                ('model', '=', self.origin_resource.__class__.__name__)])[0].id

    @classmethod
    def select_resource_models(cls):
        pool = Pool()
        all_models = ResourceMixin.get_models()
        result = []
        for model_name, translation in all_models:
            if not issubclass(pool.get(model_name), WebUIResourceMixin):
                continue
            result.append((model_name, translation))
        return result


class WebUIResourceKey(model.CodedMixin, model.CoogView):
    'Web UI Resource Key'
    __name__ = 'web.ui.resource.key'

    ir_model_resource_key = fields.Many2Many('ir.model-web.ui.resource.key',
        'web_ui_res_key', 'on_model', 'IR Model Resource Key',
            domain=[('id', 'in', Eval('filter_model'))],
            depends=['filter_model'])
    filter_model = fields.Function(fields.Many2Many('ir.model', None, None,
        'Filter Model'), 'on_change_with_filter_model')
    model_description = fields.Function(fields.Text('Model Description'),
        'get_model_description')

    @fields.depends('name', 'code')
    def on_change_with_filter_model(self, name=None):
        pool = Pool()
        all_models = pool.get('ir.model').search([])
        result = []
        for models in all_models:
            if not issubclass(pool.get(models.model), WebUIResourceMixin):
                continue
            result.append(models.id)
        return result

    def get_model_description(self, name=None):
        return '\n'.join([desc.name for desc in self.ir_model_resource_key])


class WebUIResourceMixin(model.CoogSQL):
    '''
        A Model inheriting this Mixin will have a list of web ui resource that
        will be available to easily set custom properties
    '''
    web_ui_resources = fields.One2Many('web.ui.resource', 'origin_resource',
        'Web UI Resources', delete_missing=True, target_not_indexed=True,
        help='A list of resources which will only be used through the APIs')

    def get_web_resource_by_key(self, key):
        for x in self.web_ui_resources:
            if x.key.code == key:
                return x.value
        raise KeyError


class RelationWebUIResourceKeyIRModel(model.CoogSQL, model.CoogView):
    'Relation Web UI Resource Key IR Model'
    __name__ = 'ir.model-web.ui.resource.key'

    on_model = fields.Many2One('ir.model', 'On Model', ondelete='CASCADE')
    web_ui_res_key = fields.Many2One('web.ui.resource.key',
        'Web UI Resource Key', ondelete='CASCADE')
