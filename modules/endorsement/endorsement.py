import copy

from sql import Column, Literal
from sql.conditionals import Coalesce
from sql.functions import Now

from trytond.pool import PoolMeta
from trytond.model import Model, ModelSQL, ModelView, Workflow, fields
from trytond.pyson import PYSONEncoder, Eval
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'Endorsement',
    'EndorsementField',
    'EndorsementOption',
    'EndorsementOptionField',
    ]


class EndorsementHistory:
    _history = True

    @classmethod
    def restore_history(cls, ids, datetime):
        'Restore record ids from history at the date time'
        # TODO include in ModelSQL
        transaction = Transaction()
        cursor = transaction.cursor
        table = cls.__table__()
        history = cls.__table_history__()
        columns = []
        hcolumns = []
        for fname, field in sorted(cls._fields.iteritems()):
            if hasattr(field, 'set'):
                continue
            columns.append(Column(table, fname))
            if fname == 'write_uid':
                hcolumns.append(Literal(transaction.user))
            elif fname == 'write_date':
                hcolumns.append(Now())
            else:
                hcolumns.append(Column(history, fname))

        to_delete = []
        to_update = []
        for id_ in ids:
            column_datetime = Coalesce(history.write_date, history.create_date)
            hwhere = (column_datetime <= datetime) & (history.id == id_)
            horder = column_datetime.desc
            cursor.execute(*history.select(*hcolumns,
                    where=hwhere, order_by=horder, limit=1))
            values = cursor.fetchone()
            if not values:
                # TODO replace with delete query and call to __insert_history
                to_delete.append(id_)
            else:
                to_update.append(id_)
                values = list(values)
                cursor.execute(*table.update(columns, values,
                        where=table.id == id_))
                rowcount = cursor.rowcount
                if rowcount == -1 or rowcount is None:
                    cursor.execute(*table.select(table.id,
                            where=table.id == id_))
                    rowcount = len(cursor.fetchall())
                if rowcount < 1:
                    cursor.execute(*table.insert(columns, [values]))

        # TODO to replace with call to __insert_history
        with Transaction().set_context(_datetime=datetime):
            if to_delete:
                cls.delete(cls.browse(to_delete))
            if to_update:
                cls.write(cls.browse(to_update), {})


def field_mixin(model):

    class Mixin(Model):
        name = fields.Function(fields.Char('Name'), 'get_name',
            searcher='search_name')
        field = fields.Many2One('ir.model.field', 'Field', domain=[
                ('model.model', '=', model),
                ('ttype', 'in', ['boolean', 'integer', 'char', 'float',
                        'numeric', 'date', 'datetime', 'selection',
                        'many2one']),
                ])

        @classmethod
        def __setup__(cls):
            super(Mixin, cls).__setup__()
            cls.__rpc__.update({
                    'get_keys': RPC(instantiate=0),
                    })

        def get_rec_name(self, name):
            return self.field.rec_name

        @classmethod
        def search_rec_name(cls, name, clause):
            return [('field.rec_name',) + tuple(clause[1:])]

        def get_name(self, name):
            return self.field.name

        @classmethod
        def search_name(cls, name, clause):
            return [('field.name',) + tuple(clause[1:])]

        @classmethod
        def get_keys(cls, fields):
            pool = Pool()
            FieldModel = pool.get(model)
            keys = []
            for field in fields:
                key = {
                    'id': field.id,
                    'name': field.rec_name,
                    'string': field.field.field_description,
                    'type_': field.field.ttype,
                    }
                if field.field.ttype == 'selection':
                    # TODO
                    pass
                elif field.field.ttype in ('float', 'numeric'):
                    # XXX what about PySON?
                    key['digits'] = FieldModel._fields[field.rec_name].digits
                keys.append(key)
            return keys

    return Mixin


def values_mixin(value_model):

    class Mixin(ModelSQL, ModelView):
        values = fields.Dict(value_model, 'Values')
        # applied_on need to be stored to be used as datetime_field
        applied_on = fields.Timestamp('Applied On', readonly=True)

        @classmethod
        def _view_look_dom_arch(cls, tree, type, field_children=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            values = tree.xpath('//field[@name="values"]')
            if values:
                values = values[0]
                vfields = ValueModel.search([
                        ('field.ttype', '=', 'many2one'),
                        ])
                used_ids = []
                for vfield in vfields:
                    if vfield.field.id in used_ids:
                        continue
                    field = copy.copy(values)
                    field.set('name', vfield.rec_name)
                    field.set('colspan', str(int(values.get('colspan')) / 2))
                    values.addnext(field)
                    label = copy.copy(values)
                    label.tag = 'label'
                    label.set('name', vfield.rec_name)
                    label.set('colspan', str(int(values.get('colspan')) / 2))
                    values.addnext(label)
                    used_ids.append(vfield.field.id)
            return super(Mixin, cls)._view_look_dom_arch(tree, type,
                field_children=field_children)

        @classmethod
        def fields_get(cls, fields_names=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            encoder = PYSONEncoder()

            fields = super(Mixin, cls).fields_get(fields_names=fields_names)
            if fields_names is None:
                fields_names = []

            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            used_ids = []
            for vfield in vfields:
                if vfield.field.id in used_ids:
                    continue
                if vfield.rec_name in fields_names or not fields_names:
                    fields[vfield.rec_name] = {
                        'type': 'many2one',
                        'name': vfield.rec_name,
                        'string': vfield.field.field_description,
                        'relation': vfield.field.relation,
                        'states': encoder.encode({
                                'invisible': ~Eval('values', {}).contains(
                                    str(vfield.rec_name)),
                                'readonly': cls.values.states.get('readonly',
                                    False),
                                }),
                        'datetime_field': 'applied_on',
                        'depends': (['values', 'applied_on']
                            + cls.values.depends),
                        }
                    used_ids.append(vfield.field.id)
            return fields

        @classmethod
        def read(cls, ids, fields_names=None):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            vfields = dict((f.rec_name, f) for f in vfields)
            to_read = set()
            to_compute = set()
            to_compute_related = {}

            for field_name in fields_names or []:
                if '.' in field_name:
                    local_field_name, related_field_name = (
                        field_name.split('.', 1))
                    if local_field_name in vfields:
                        to_compute.add(local_field_name)
                        to_compute_related.setdefault(local_field_name,
                            []).append(related_field_name)
                        continue
                if field_name in vfields:
                    to_compute.add(field_name)
                else:
                    to_read.add(field_name)
            if to_compute:
                to_read.add('values')

            result = super(Mixin, cls).read(ids, fields_names=list(to_read))

            for row in result:
                for field_name in to_compute:
                    if row['values']:
                        row[field_name] = row['values'].get(field_name)
                    else:
                        row[field_name] = None

            related2values = {}
            for field_name in to_compute_related:
                Target = pool.get(vfields[field_name].field.relation)
                related2values.setdefault(field_name, {})
                for target in Target.read(
                        [r[field_name] for r in result if r[field_name]],
                        to_compute_related[field_name]):
                    target_id = target.pop('id')
                    values = related2values[field_name].setdefault(
                        target_id, {})
                    for row in result:
                        values[row['id']] = target
            if to_compute_related:
                for row in result:
                    for field_name in to_compute_related:
                        for related in to_compute_related[field_name]:
                            related_name = '.'.join((field_name, related))
                            value = None
                            if row[field_name]:
                                value = related2values[field_name][
                                    row[field_name]][row['id']][related]
                            row[related_name] = value
            return result

        @classmethod
        def default_get(cls, fields, with_rec_name=True):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])
            vfields = list(set([f.rec_name for f in vfields]))
            fields = [f for f in fields if f not in vfields]
            return super(Mixin, cls).default_get(fields,
                with_rec_name=with_rec_name)

        @staticmethod
        def convert_values(values):
            pool = Pool()
            ValueModel = pool.get(value_model)
            vfields = ValueModel.search([
                    ('field.ttype', '=', 'many2one'),
                    ])

            values = values.copy()

            new_values = {}
            for field in vfields:
                name = field.rec_name
                if name in values and name not in new_values:
                    new_values[name] = values.pop(name)
            if new_values:
                values.setdefault('values', {}).update(new_values)
            return values

        @classmethod
        def create(cls, vlist):
            vlist = [cls.convert_values(v) for v in vlist]
            return super(Mixin, cls).create(vlist)

        @classmethod
        def write(cls, records, values):
            if 'values' in values:
                super(Mixin, cls).write(records, cls.convert_values(values))
            else:
                for record in records:
                    values = values.copy()
                    values['values'] = record.values
                    super(Mixin, cls).write([record],
                        cls.convert_values(values))

    return Mixin


def relation_mixin(value_model, field, model, name):

    class Mixin(values_mixin(value_model)):
        action = fields.Selection([
                ('add', 'Add'),
                ('update', 'Update'),
                ('remove', 'Remove'),
                ], 'Action')
        relation = fields.Integer('Relation',
            states={
                'required': Eval('action').in_(['update', 'remove']),
                'invisible': Eval('action') == 'add',
                },
            depends=['action'])

        @classmethod
        def __setup__(cls):
            super(Mixin, cls).__setup__()
            cls.values.states = {
                'invisible': Eval('action') == 'remove',
                }
            cls.values.depends = ['action']

        @staticmethod
        def default_action():
            return 'add'

        def get_relation(self, name):
            return self.relation

        @classmethod
        def set_relation(cls, records, name, value):
            cls.write(records, {
                    'relation': value,
                    })

        @property
        def apply_values(self):
            values = (self.values if self.values else {}).copy()
            if self.action == 'add':
                return ('create', [values])
            elif self.action == 'update':
                return ('write', [getattr(self, field).id], values)
            elif self.action == 'remove':
                return ('delete', [getattr(self, field).id])

    setattr(Mixin, field, fields.Function(fields.Many2One(model, name,
                datetime_field='applied_on',
                states={
                    'required': Eval('action').in_(['update', 'remove']),
                    'invisible': Eval('action') == 'add',
                    },
                depends=['action']),
            'get_relation', setter='set_relation'))

    return Mixin


class Contract(object, EndorsementHistory):
    __name__ = 'contract'


class ContractOption(object, EndorsementHistory):
    __name__ = 'contract.option'


class Endorsement(values_mixin('endorsement.field'),
        Workflow, ModelSQL, ModelView):
    'Endorsement'
    __name__ = 'endorsement'

    template = fields.Many2One('endorsement.template', 'Template',
        states={'required': True})
    contract = fields.Many2One('contract', 'Contract', required=True,
        datetime_field='applied_on',
        states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('applied', 'Applied'),
            ], 'State', readonly=True)
    options = fields.One2Many('endorsement.option', 'endorsement', 'Options',
        states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'contract', 'template'],
        context={'template': Eval('template')})

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('template', '=', Eval('template'))]
        cls.values.depends = ['state', 'template']
        cls.applied_on.states = {
            'required': Eval('state') == 'applied',
            }
        cls.applied_on.depends = ['state']
        cls._error_messages.update({
                'not_latest_applied': ('Endorsement "%s" is not the latest '
                    'applied.')
                })
        cls._transitions |= set((
                ('draft', 'applied'),
                ('applied', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['applied']),
                    },
                'apply': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, endorsements):
        pool = Pool()
        Contract = pool.get('contract')
        ContractOption = pool.get('contract.option')

        for endorsement in endorsements:
            latest_applied, = cls.search([
                    ('contract', '=', endorsement.contract.id),
                    ('state', '=', 'applied'),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != endorsement:
                cls.raise_user_error('not_latest_applied',
                    endorsement.rec_name)

            hcontract = endorsement.contract
            contract = Contract(endorsement.contract.id)

            Contract.restore_history([contract.id], endorsement.applied_on)
            option_ids = set((o.id
                    for o in (contract.options + hcontract.options)))
            ContractOption.restore_history(list(option_ids),
                endorsement.applied_on)

            endorsement.set_applied_on(None)
            endorsement.state = 'draft'
            endorsement.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('applied')
    def apply(cls, endorsements):
        pool = Pool()
        Contract = pool.get('contract')
        for endorsement in endorsements:
            contract = endorsement.contract
            endorsement.set_applied_on(contract.write_date
                or contract.create_date)
            Contract.write([contract], endorsement.apply_values)
            endorsement.save()

    def set_applied_on(self, datetime):
        self.applied_on = datetime
        for option in self.options:
            option.applied_on = datetime
        self.options = list(self.options)

    @property
    def apply_values(self):
        values = (self.values if self.values else {}).copy()
        values['options'] = options = []
        for option in self.options:
            options.append(option.apply_values)
        return values


class EndorsementField(field_mixin('contract'), ModelSQL, ModelView):
    'Endorsement Field'
    __name__ = 'endorsement.field'

    template = fields.Many2One('endorsement.template', 'Template',
        states={'invisible': True}, ondelete='CASCADE')


class EndorsementOption(relation_mixin('endorsement.option.field', 'option',
            'contract.option', 'Options'),
        ModelSQL, ModelView):
    'Endorsement Option'
    __name__ = 'endorsement.option'

    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        select=True)
    template = fields.Function(
        fields.Many2One('endorsement.template', 'Template'),
        'get_template')

    @classmethod
    def __setup__(cls):
        super(EndorsementOption, cls).__setup__()
        cls.values = copy.copy(cls.values)
        cls.values.domain = [('template', '=', Eval('template'))]
        cls.values.depends = ['template']

    @classmethod
    def default_template(cls):
        if 'template' in Transaction().context:
            return Transaction().context.get('template')
        return None

    def get_template(self, name):
        return self.endorsement.template


class EndorsementOptionField(field_mixin('contract.option'),
        ModelSQL, ModelView):
    'Endorsement Option Field'
    __name__ = 'endorsement.option.field'

    template = fields.Many2One('endorsement.template', 'Template',
        states={'invisible': True}, ondelete='CASCADE')
