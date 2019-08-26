# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column, Literal, Window
from sql.aggregate import Max
from sql.functions import RowNumber

from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder

from trytond.modules.coog_core import model, UnionMixin, fields


def generate_hierarchy(config, classes=None, counter=0):
    '''
        Provides a high-level abstraction to create complex UnionMixin trees.

        It should be called with only a config dictionnary, and it will return
        a tuple:

        >>> generate_hierarchy(my_config_file)
        ([Model1, Model2, ...], ActionWizard)

        Model1 / Model2 / etc should be registered as models in the module's
        register method, and ActionWizard as a Wizard.

        The config dict describes the nodes of the union mixin. A node has the
        following attributes:

        - node_name: The name of the model that will be generated
        - type: specifies the node type:
            * 'root': Only for the root node (obviously)
            * 'node': Nodes that are only used for grouping the data
            * 'data': Will return a list of instances at runtime, matching the
                node description
        - model: For non-root nodes, the model which will be targeted by the
            node. Basically, the model on which the search will take place
        - parent_field: The field of the "model" which should be used to create
            the hierarchy
        - main_field: For "root" type nodes, the model on which the "joining"
            will be done. Think of it as the model from which the union mixin
            will be opened. For other nodes, should be the field of the node's
            target model which will be used to match the main model of the
            mixin
        - name: For "node" types, the name that will be used for the node
        - <optional> icon: The icon that will be used on the node. If not set,
            the node's instance icon will be used if available
        - <optional> domain: A domain that will be applied when searching in
            the node
        - <optional> name_func: For data nodes, a function that will be used to
            name the node. It will be called with the node's instance as a
            parameter. If not set, the node's instance rec_name will be used
        - <optional> childs: A list of (nested) configuration for nodes that
            should be display below this one

        Creating the xml entries for the models must still be done manually.
        A tree view (+ act windows) on the root model is the minimum, as well
        as setting the tree action to the ActionWizard model (named as the root
        "node_name" + '.open')

        Sample config (for parties):

        {
            'node_name': 'party.tree',
            'type': 'root',
            'main_field': 'party.party',
            'name': 'Party Tree',
            'childs': [{
                    'node_name': 'party.tree.person_root',
                    'model': 'party.party',
                    'main_field': 'id',
                    'type': 'node',
                    'domain': [('is_person', '=', True)],
                    'childs': [{
                            'node_name': 'party.tree.person',
                            'model': 'party.party',
                            'main_field': 'id',
                            'type': 'data',
                            'domain': [('is_person', '=', True)],
                            'icon': 'person',
                            'childs': [{
                                    'node_name': 'party.tree.person.address',
                                    'model': 'party.address',
                                    'main_field': 'party',
                                    'type': 'data',
                                    }],
                            }],
                    }, {
                    'node_name': 'party.tree.company_root',
                    'model': 'party.party',
                    'main_field': 'id',
                    'type': 'node',
                    'domain': [('is_person', '=', False)],
                    'childs': [{
                            'node_name': 'party.tree.company',
                            'model': 'party.party',
                            'main_field': 'id',
                            'type': 'data',
                            'domain': [('is_person', '=', False)],
                            'icon': 'company',
                            'childs': [{
                                    'node_name': 'party.tree.company.address',
                                    'model': 'party.address',
                                    'main_field': 'party',
                                    'type': 'data',
                                    }],
                            }],
                    }],
            ]
        }
    '''
    if classes is None:
        classes = []

    for idx, elem in enumerate(config.get('childs', [])):
        generate_hierarchy(elem, classes=classes, counter=counter + idx)
        classes[-1][1]._counter = counter + idx
        classes[-1][1]._parent_model_name = config['node_name']

    classes_dict = {m.__name__: c for c, m in classes}

    if config['type'] == 'root':

        class Root(UnionMixin, model.CoogSQL, model.CoogView,
                model.ExpandTreeMixin):
            'Hierarchy'
            __name__ = config['node_name']

            parent = fields.Many2One(config['node_name'], 'Parent',
                ondelete='SET NULL')
            childs = fields.One2Many(config['node_name'], 'parent', 'Childs',
                target_not_required=True)
            main_field = fields.Many2One(config['main_field'], 'Party',
                ondelete='SET NULL')
            icon = fields.Function(fields.Char('Icon'), 'getter_icon')
            sequence = fields.Integer('Sequence')

            @classmethod
            def __setup__(cls):
                super(Root, cls).__setup__()
                cls._order = [('sequence', 'ASC')]

            @classmethod
            def union_models(cls):
                return [elem['node_name'] for elem, _ in classes]

            @classmethod
            def union_field(cls, name, Model):
                for elem, klass in classes:
                    if Model.__name__ == elem['node_name']:
                        if name == 'parent':
                            return Model.parent
                        if name == 'main_field':
                            return Model.main_field
                        if name == 'sequence':
                            return Model.sequence

            def get_rec_name(self, name):
                return self.union_unshard(self.id).rec_name

            def getter_icon(self, name):
                return self.union_unshard(self.id).icon

            @classmethod
            def table_query(cls):
                return super(Root, cls).table_query()

        class Open(Wizard):
            'Open'
            __name__ = config['node_name'] + '.open'

            start_state = 'open'
            open = model.VoidStateAction()

            def do_open(self, action):
                pool = Pool()
                Root = pool.get(config['node_name'])
                context = Transaction().context
                node = Root(context['active_id'])
                record = Root.union_unshard(context['active_id'])

                conf = classes_dict[record.__name__]
                if conf.get('no_action'):
                    return {}, {}

                action = {}
                domain = []
                if conf['type'] == 'node':
                    childs = [Root.union_unshard(x.id) for x in node.childs]
                    if childs:
                        action['res_model'] = childs[0].instance.__name__
                        action['res_ids'] = [x.instance.id
                            for x in childs
                            if x.__name__ == childs[0].__name__]
                        domain = [('id', 'in', action['res_ids'])]
                        action['views'] = [(None, 'tree'), (None, 'form')]
                    else:
                        return {}, {}
                elif conf['type'] == 'data':
                    action['res_model'] = record.instance.__name__
                    domain = [('id', '=', record.instance.id)]
                    action['views'] = [(None, 'form')]
                    action['res_id'] = record.instance.id
                action['pyson_domain'] = PYSONEncoder().encode(domain)
                action['id'] = None
                action['type'] = 'ir.action.act_window'
                action['pyson_order'] = '[]'
                action['pyson_search_value'] = '[]'
                action['domains'] = []
                action['context_model'] = None
                action['rec_name'] = record.rec_name
                action['name'] = record.rec_name
                return action, {}

        for _, elem in classes:
            elem._main_field_model_name = config['main_field']
        return [Root] + [x for _, x in classes], Open

    if config['type'] == 'node':

        class Node(model.CoogSQL):
            'Node'
            __name__ = config['node_name']

            icon = fields.Function(
                fields.Char('Icon'),
                'getter_icon')
            parent = fields.Many2One('set in parent', 'Parent',
                ondelete='SET NULL')
            main_field = fields.Many2One('set in parent', 'Main Field',
                ondelete='SET NULL')
            sequence = fields.Integer('Sequence')

            @classmethod
            def __setup__(cls):
                super(Node, cls).__setup__()
                cls.parent.model_name = cls._parent_model_name
                cls.main_field.model_name = cls._main_field_model_name

            @classmethod
            def table_query(cls):
                pool = Pool()
                Target = pool.get(config['model'])
                target = Target.__table__()
                where = None
                if config.get('domain', None):
                    domain = Target.search(config['domain'], query=True)
                    where = target.id.in_(domain)

                group_by = [Column(target, config.get('parent_field',
                            config['main_field']))]

                return target.select(
                    Max(Column(target, config.get('parent_field',
                                config['main_field']))).as_('id'),
                    Max(target.create_uid).as_('create_uid'),
                    Max(target.create_date).as_('create_date'),
                    Max(target.write_uid).as_('write_uid'),
                    Max(target.write_date).as_('write_date'),
                    Max(Column(target, config.get('parent_field',
                                config['main_field']))).as_('parent'),
                    Max(Column(target, config['main_field'])).as_(
                        'main_field'),
                    Literal(cls._counter).as_('sequence'),
                    where=where,
                    group_by=group_by,
                    )

            def getter_icon(self, name):
                return config['icon']

            def get_rec_name(self, name):
                return config['name']

        classes.append((config, Node))

    if config['type'] == 'data':

        class Data(model.CoogSQL):
            'Data'
            __name__ = config['node_name']

            icon = fields.Function(
                fields.Char('Icon'),
                'getter_icon')
            parent = fields.Many2One('set in parent', 'Parent',
                ondelete='SET NULL')
            main_field = fields.Many2One('set in parent', 'Main Field',
                ondelete='SET NULL')
            instance = fields.Many2One(config['model'], 'Instance',
                ondelete='SET NULL')
            sequence = fields.Integer('Sequence')

            @classmethod
            def __setup__(cls):
                super(Data, cls).__setup__()
                cls.parent.model_name = cls._parent_model_name
                cls.main_field.model_name = cls._main_field_model_name

            @classmethod
            def table_query(cls):
                pool = Pool()
                Target = pool.get(config['model'])
                target = Target.__table__()
                where = None
                if config.get('domain', None):
                    domain = Target.search(config['domain'], query=True)
                    where = target.id.in_(domain)

                order_fields = config.get('order_fields', [])
                if order_fields:
                    order_by = []
                    for field_, order in order_fields:
                        if order == 'DESC':
                            order_by.append(Column(target, field_).desc)
                        else:
                            order_by.append(Column(target, field_).asc)
                    sequence_col = RowNumber(window=Window([
                                Column(target, config.get('parent_field',
                                        config['main_field']))
                                ], order_by=order_by))
                else:
                    sequence_col = Literal(cls._counter)
                return target.select(
                    target.id,
                    target.id.as_('instance'),
                    Column(target, config['main_field']).as_('main_field'),
                    Column(target, config.get('parent_field',
                            config['main_field'])).as_('parent'),
                    target.create_uid,
                    target.create_date,
                    target.write_uid,
                    target.write_date,
                    sequence_col.as_('sequence'),
                    where=where)

            def getter_icon(self, name):
                if 'icon' in config:
                    return config['icon']
                return getattr(self.instance, 'icon', getattr(self.instance,
                        'get_icon', lambda: '')(None))

            def get_rec_name(self, name):
                if 'name_func' in config:
                    return config['name_func'](self.instance)
                return getattr(self.instance, 'get_synthesis_rec_name',
                    lambda x: self.instance.rec_name)(None)

        classes.append((config, Data))
