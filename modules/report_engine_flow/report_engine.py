# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import inspect
import os

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Or
from trytond.model import Unique
from trytond.config import config

from trytond.modules.coog_core import fields, model, coog_string, utils

from trytond.server_context import ServerContext

import func_library

__metaclass__ = PoolMeta

__all__ = [
    'ReportGenerate',
    'ReportTemplate',
    'ReportCreate',
    'FlowVariable',
    'TemplateVariableRelation',
    ]

INSTR_TYPES = [
    ('data', 'Data'), ('for', 'For'),
    ('if', 'If'), ('free', 'Free'),
    ('function', 'Function'),
    ]

FLAT = Or(Eval('kind') == 'data', Eval('kind') == 'free',
    Eval('kind') == 'function')


class TemplateVariableRelation(model.CoogSQL, model.CoogView):
    'Template Variable Relation'

    __name__ = 'report.template.flow_variable.relation'

    template = fields.Many2One('report.template', 'Template',
        ondelete='CASCADE', required=True, select=True)
    variable = fields.Many2One('report.flow.variable', 'Variable',
        ondelete='CASCADE', required=True, domain=[
            ('variable', '=', None),
            ])
    order = fields.Integer('Order', states={'invisible': True},
        required=True)
    name = fields.Function(fields.Char('Name'),
        'get_variable_field')
    description = fields.Function(fields.Char('Description'),
        'get_variable_field')
    kind = fields.Function(fields.Char('Kind'),
        'get_variable_field')
    data = fields.Function(fields.Char('Data'),
        'get_variable_field')

    def get_variable_field(self, name):
        if name == 'kind':
            return coog_string.translate_value(self.variable, 'kind')
        return getattr(self.variable, name)

    @fields.depends('template')
    def on_change_with_order(self, name=None):
        # TODO: Delete this method when client is patched:
        # See https://bugs.tryton.org/issue6439
        if not self.template:
            return 0
        previous_order = 0
        for relation in self.template.variables_relation:
            if relation == self:
                break
            previous_order = relation.order
        return previous_order + 1


class FlowVariable(model.CoogSQL, model.CoogView):
    'Flow Variable'

    __name__ = 'report.flow.variable'

    _rec_name = 'description'
    name = fields.Function(fields.Char('Name'),
        'get_name', searcher='search_name')
    description = fields.Char('Description', required=True, select=True)
    kind = fields.Selection(INSTR_TYPES, 'Kind', required=True)
    variable = fields.Many2One('report.flow.variable', 'Variable',
        ondelete='CASCADE', select=True)
    variables = fields.One2Many('report.flow.variable', 'variable',
        'Variables', states={'invisible': FLAT}, target_not_required=True,
        depends=['kind'], order=[('order', 'ASC')], delete_missing=True)
    data = fields.Char('Data', states={'invisible': Not(FLAT)},
        depends=['kind'])
    if_statement = fields.Char('If', states={
            'invisible': Eval('kind') != 'if',
            'required': Eval('kind') == 'if',
            }, depends=['kind'])
    else_statement = fields.One2Many('report.flow.variable', 'else_reverse',
        'Else', states={'invisible': Eval('kind') != 'if'},
        target_not_required=True, depends=['kind'], order=[('order', 'ASC')],
        delete_missing=True)
    else_reverse = fields.Many2One('report.flow.variable', 'Else Reverse',
        ondelete='CASCADE', select=True)
    for_object_statement = fields.Char('For', states={
            'invisible': Eval('kind') != 'for',
            'required': Eval('kind') == 'for',
            }, depends=['kind'])
    for_objects_statement = fields.Char('In', states={
            'invisible': Eval('kind') != 'for',
            'required': Eval('kind') == 'for',
    }, depends=['kind'])
    generated_code = fields.Function(fields.Text(
            'Generated Code'), 'get_generated_code')
    separator = fields.Char('Separator')
    order = fields.Integer('Order', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(FlowVariable, cls).__setup__()
        table = cls.__table__()
        cls.lambdas = {
            'for': lambda this, separator: ('{%%for %s in %s%%}' % (
                    this.for_object_statement, this.for_objects_statement),
                '{%%end%%}%s' % separator),
            'if': lambda this, separator: (
                    '{%%choose%%}{%%when %s%%}' % this.if_statement,
                    '{%%end%%}{%%otherwise%%}%s{%%end%%}%s{%%end%%}'
                    % (this.get_else_generated_code(this), separator)),
            'data': lambda this, separator: ('${%s if (%s) else %s}%s' % (
                this.data, this.data, cls._default_not_data(this), separator),
                ''),
            'free': lambda this, separator: (this.data + separator, ''),
            'function': lambda this, separator: ('${%s}%s' % (
                this.data, separator), ''),
            }
        cls._sql_constraints += [
            ('desc_uniq', Unique(table, table.description),
                'The description must be unique.')]

    @classmethod
    def _default_not_data(cls, node):
        return '""'

    @classmethod
    def default_separator(cls):
        return ''

    def get_generated_code(self, name=None):
        return self.build_output()

    @classmethod
    def get_eval_methods(cls):
        return func_library.EVAL_METHODS

    @classmethod
    def available_data_completion(cls, data, kind):
        if kind != 'function':
            return ['']
        result = []
        for key, fct in cls.get_eval_methods():
            if data in key:
                fct_definition = inspect.getargspec(fct)
                args = tuple(fct_definition[0])
                result.append(key + str(args).replace('\'', ''))
        return result

    @fields.depends('kind', 'data')
    def autocomplete_data(self):
        if self.data and self.kind:
            return self.available_data_completion(self.data, self.kind)
        return ['']

    @classmethod
    def kind_fields(cls):
        return ['if_statement', 'for_object_statement',
            'for_objects_statement', 'data']

    @classmethod
    def search_name(cls, name, clause):
        clauses = ['OR']
        like = clause[2].strip('%') if clause[1] == 'ilike' else clause[2]
        kind_value, data_value = '', ''
        if ':' in like:
            kind_value, data_value = like.split(':')
            if clause[1] == 'ilike':
                kind_value = '%%%s%%' % kind_value.strip(' ')
                data_value = '%%%s%%' % data_value.strip(' ')
        for _field in cls.kind_fields():
            clauses.append(
                ((_field, clause[1], data_value) if data_value else
                     (_field,) + tuple(clause[1:]))
                )
        if kind_value:
            return [('kind', clause[1], kind_value), clauses]
        else:
            clauses.append(('kind',) + tuple(clause[1:]))
        return clauses

    def get_name(self, name=None):
        name_resolver = {
            'for': lambda this: '%s - %s' % (this.for_object_statement,
                this.for_objects_statement),
            'if': lambda this: this.if_statement,
            'data': lambda this: this.data,
            'free': lambda this: this.data,
            'function': lambda this: this.data,
            }
        return self.kind + ': %s' % name_resolver[self.kind](self)

    @classmethod
    def get_separator(cls, node, leaf, last):
        return str(node.separator).decode('string_escape')

    def get_else_generated_code(self, node):
        output = ''
        for it, variable in enumerate(node.else_statement, start=1):
            leaf = not variable.variables
            last = len(node.else_statement) == it
            output += node.build_output(node=variable, leaf=leaf, last=last)
        return output

    def build_output(self, node=None, leaf=True, last=True, separator=None):
        if not node:
            node = self
        separator = separator if separator is not None else \
            self.get_separator(node, leaf, last)
        output = ''
        begin, end = self.lambdas[node.kind](node, separator)
        output += begin
        if node.kind in ('for', 'if') and node.variables:
            for it, variable in enumerate(node.variables, start=1):
                leaf = not variable.variables
                last = len(node.variables) == it
                output += node.build_output(node=variable, leaf=leaf,
                    last=last)
        output += end
        return output


class ReportGenerate:
    __name__ = 'report.generate'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReportGenerate, cls).get_context(records, data)
        report_context.update({x[0]: getattr(func_library, 'eval_%s' % x[0])
                for x in func_library.EVAL_METHODS})
        from itertools import groupby

        def copy_groupby(*args, **kwargs):
            for key, values in groupby(*args, **kwargs):
                yield key, list(values)
        report_context['groupby'] = copy_groupby
        return report_context

    @classmethod
    def process_default_flux(cls, ids, data, **kwargs):
        from genshi.template import NewTextTemplate
        selected_template = Pool().get('report.template')(
            data['doc_template'][0])
        records = cls._get_records(ids, data['model'], data)
        template_content = selected_template.generated_code
        tmpl = NewTextTemplate(template_content)
        result = tmpl.generate(**cls.get_context(records, data)).render()
        filename, ext = os.path.splitext(
            selected_template.genshi_evaluated_output_filename)
        return ext[1:], bytearray(result, 'utf-8'), False, filename


class ReportTemplate:
    __name__ = 'report.template'

    variables_relation = fields.One2Many(
        'report.template.flow_variable.relation', 'template',
        'Flow Variables Relation', order=[('order', 'ASC')],
        delete_missing=True, depends=['input_kind'])
    generated_code = fields.Function(fields.Text('Generated code',
            states={
                'invisible': Eval('input_kind') != 'flow',
                }, depends=['input_kind']),
        'get_generated_code')
    override_loop = fields.Boolean('Override Loop',
        states={'invisible': Eval('input_kind') != 'flow',
            }, depends=['input_kind'])
    loop_condition = fields.Char('Object Line Loop',
        states={'invisible': Or(Eval('input_kind') != 'flow',
                ~Eval('override_loop')),
            }, depends=['input_kind', 'override_loop'],
        help='Genshi condition which define the loop condition to generate the '
        'flow lines')

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'output_mixin': 'You cannot print a flow'
                ' and a model at the same time',
                'input_flow_variable': 'From Flow Variable',
                'process_method_default_flux': 'Default Flux'
                })
        for fname in ['modifiable_before_printing',
                'split_reports', 'document_desc',
                'format_for_internal_edm', 'versions']:
            field = getattr(cls, fname)
            field.states['invisible'] = Or(Eval('input_kind') == 'flow',
                field.states.get('invisible', False))
            field.depends.append('input_kind')
        cls.output_filename.states['required'] |= (Eval('input_kind') ==
            'flow')
        cls.output_filename.depends.append('input_kind')

    @classmethod
    def view_attributes(cls):
        return super(ReportTemplate, cls).view_attributes() + [(
                '/form/notebook/page[@id="versions"]', 'states',
                {'invisible': getattr(cls, 'versions').states.get(
                        'invisible')}),
            ('/form/notebook/page[@id="generated_code"]', 'states',
                {'invisible': Eval('input_kind') != 'flow'}),
            ('/form/notebook/page[@id="flow"]', 'states',
                {'invisible': Eval('input_kind') != 'flow'}),
            ]

    def get_selected_version(self, date, language):
        if self.input_kind == 'flow':
            return None
        return super(ReportTemplate, self).get_selected_version(date,
            language)

    @classmethod
    def get_possible_input_kinds(cls):
        return super(ReportTemplate, cls).get_possible_input_kinds() + \
            [('flow', cls.raise_user_error('input_flow_variable',
                        raise_exception=False))]

    def get_generated_code(self, name=None):
        if not self.override_loop:
            output = '{%for record in records%}'
        else:
            output = self.loop_condition
        for var_relation in self.variables_relation:
            output += var_relation.variable.generated_code
        output += '\n'
        output += '{%end%}'
        return output

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'flow':
            return [('default_flux',
                    self.raise_user_error('process_method_default_flux',
                        raise_exception=False))]
        return super(ReportTemplate, self).get_possible_process_methods()

    @fields.depends('input_kind', 'split_reports')
    def on_change_input_kind(self):
        super(ReportTemplate, self).on_change_input_kind()
        if self.input_kind == 'flow':
            self.split_reports = False
            self.format_for_internal_edm = ''
        else:
            self.variables_relations = []
            self.override_loop = False
            self.loop_condition = ''

    def print_reports(self, reports, context_):
        if self.input_kind != 'flow':
            return super(ReportTemplate, self).print_reports(reports, context_)
        pool = Pool()
        ReportModel = pool.get('report.create', type='wizard')
        if self.export_dir:
            ReportGenerate = pool.get('report.generate', type='report')
            data = context_['reporting_data']
            report_template = pool.get('report.template')(
                data['doc_template'][0])

            records = ReportGenerate._get_records(
                data['ids'], data['model'], data)
            with ServerContext().set_context(
                    genshi_context=ReportGenerate.get_context
                    (records, data)):
                filename = report_template.get_export_dirname()
        else:
            filename = report_template.get_export_dirname()
        for report in reports:
            ReportModel.create_flow_file(os.path.join(filename,
                    report['report_name']), report['data'])


class ReportCreate:
    __name__ = 'report.create'

    def report_execute(self, ids, doc_template, report_context):
        if doc_template.input_kind != 'flow':
            return super(ReportCreate, self).report_execute(
                ids, doc_template, report_context)
        ReportModel = Pool().get('report.generate', type='report')
        ext, filedata, prnt, file_basename = ReportModel.execute(ids,
            report_context)
        filename = '%s.%s' % (file_basename, ext)
        records = ReportModel._get_records(ids, report_context['model'],
            report_context)
        report_context = ReportModel.get_context(records, report_context)
        with ServerContext().set_context(genshi_context=report_context):
            filename = os.path.join(doc_template.get_export_dirname(),
                filename)
            created_file = self.create_flow_file(filename, filedata)
        return {
            'generated_report': created_file,
            'server_filepath': created_file,
            'file_basename': file_basename,
            'extension': ext,
            'template': doc_template,
            }

    @classmethod
    def create_flow_file(cls, filepath, content):
        temporary_folder = config.get('TMP', 'folder') or '/tmp/'
        with utils.safe_open(filepath, 'ab',
                lock_directory=temporary_folder) as _file:
            _file.write(content)
        return filepath

    def transition_generate(self):
        next_state = super(ReportCreate, self).transition_generate()
        if self.select_template.template.input_kind != 'flow':
            return next_state
        return 'end'
