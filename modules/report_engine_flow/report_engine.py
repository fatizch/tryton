# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import inspect
import os
import time
import datetime

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Not, Or
from trytond.config import config
from trytond.model import Unique

from trytond.modules.coog_core import fields, model, coog_string

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
    order = fields.Integer('Order', states={'invisible': True})
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
        'Variables', states={'invisible': FLAT},
        depends=['kind'], order=[('order', 'ASC')], delete_missing=True)
    data = fields.Char('Data', states={'invisible': Not(FLAT)},
        depends=['kind'])
    if_statement = fields.Char('If', states={
            'invisible': Eval('kind') != 'if',
            'required': Eval('kind') == 'if',
            }, depends=['kind'])
    else_statement = fields.One2Many('report.flow.variable', 'else_reverse',
        'Else', states={'invisible': Eval('kind') != 'if'},
        depends=['kind'], order=[('order', 'ASC')], delete_missing=True)
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
                this.data, this.data, cls.default_not_data(this), separator),
                ''),
            'free': lambda this, separator: (this.data + separator, ''),
            'function': lambda this, separator: ('${%s}%s' % (
                this.data, separator), ''),
            }
        cls._sql_constraints += [
            ('desc_uniq', Unique(table, table.description),
                'The description must be unique.')]

    @classmethod
    def default_not_data(cls, node):
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
    def execute(cls, ids, data, immediate_conversion=False):
        template, = data['doc_template']
        if template.output_kind == 'flow':
            method_name = 'process_%s' % template.output_method
            if hasattr(cls, method_name):
                return getattr(cls, method_name)(ids, data)
            return '', '', False, ''
        return super(ReportGenerate, cls).execute(ids, data,
            immediate_conversion)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReportGenerate, cls).get_context(records, data)
        report_context.update({x[0]: getattr(func_library, 'eval_%s' % x[0])
                for x in func_library.EVAL_METHODS})
        return report_context

    @classmethod
    def process_default(cls, ids, data):
        from genshi.template import NewTextTemplate
        timestamp = datetime.datetime.fromtimestamp(time.time()
            ).strftime('%Y%m%d%H%f')
        selected_template = data['doc_template'][0]
        records = cls._get_records(ids, data['model'], data)
        template_content = selected_template.generated_code
        tmpl = NewTextTemplate(template_content)
        result = tmpl.generate(**cls.get_context(records, data)).render()
        return 'txt', bytearray(result), False, 'COOG_%s' % timestamp


class ReportTemplate:
    __name__ = 'report.template'

    output_method = fields.Selection('get_possible_output_methods',
        'Output method', states={
            'invisible': Eval('output_kind') == 'model',
            'required': Eval('output_kind') == 'flow',
            }, depends=['output_kind'])
    variables_relation = fields.One2Many(
        'report.template.flow_variable.relation', 'template',
        'Flow Variables Relation', order=[('order', 'ASC')],
        delete_missing=True, depends=['output_kind'])
    generated_code = fields.Function(fields.Text('Generated code',
            states={
                'invisible': Eval('output_kind') != 'flow',
                }, depends=['output_kind']),
        'get_generated_code')

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls._error_messages.update({
                'output_mixin': 'You cannot print a flow'
                ' and a model at the same time',
                })
        for fname in ['modifiable_before_printing', 'convert_to_pdf',
                'split_reports', 'template_extension', 'document_desc',
                'export_dir', 'format_for_internal_edm']:
            field = getattr(cls, fname)
            field.states['invisible'] = Or(Eval('output_kind') == 'flow',
                field.states.get('invisible', False))
            field.depends.append('output_kind')

    @classmethod
    def default_output_method(cls):
        return ''

    @classmethod
    def view_attributes(cls):
        return super(ReportTemplate, cls).view_attributes() + [(
                '/form/notebook/page[@id="versions"]', 'states',
                {'invisible': Eval('output_kind') == 'flow'}),
            ('/form/notebook/page[@id="generated_code"]', 'states',
                {'invisible': Eval('output_kind') != 'flow'}),
            ('/form/notebook/page[@id="flow"]', 'states',
                {'invisible': Eval('output_kind') != 'flow'}),
            ]

    @classmethod
    def get_possible_output_kinds(cls):
        return super(ReportTemplate, cls).get_possible_output_kinds() + \
            [('flow', 'From Variables')]

    def get_generated_code(self, name=None):
        output = '{%for record in records%}'
        for var_relation in self.variables_relation:
            output += var_relation.variable.generated_code
        output += '\n'
        output += '{%end%}'
        return output

    @classmethod
    def get_possible_output_methods(cls):
        return [('', ''), ('default', 'Default')]

    @fields.depends('output_kind', 'split_reports', 'convert_to_pdf')
    def on_change_output_kind(self):
        if self.output_kind == 'flow':
            self.split_reports = False
            self.convert_to_pdf = False

    def print_reports(self, reports, context_):
        if self.output_kind != 'flow':
            return super(ReportTemplate, self).print_reports(reports, context_)
        ReportModel = Pool().get('report.create', type='wizard')
        for report in reports:
            ReportModel.create_flow_file(report['report_name'], report['data'])


class ReportCreate:
    __name__ = 'report.create'

    def report_execute(self, ids, doc_template, report_context, reports):
        if doc_template.output_kind != 'flow':
            return super(ReportCreate, self).report_execute(
                ids, doc_template, report_context, reports)
        else:
            ReportModel = Pool().get('report.generate', type='report')
            ext, filedata, prnt, file_basename = ReportModel.execute(ids,
                report_context, immediate_conversion=False)
            filename = '%s.%s' % (file_basename, ext)
            created_file = self.create_flow_file(filename, filedata)
            reports.append({
                    'generated_report': created_file,
                    'server_filepath': created_file,
                    'file_basename': file_basename,
                    'template': doc_template,
                    })
            return ext, filedata, prnt, file_basename

    @classmethod
    def create_flow_file(cls, file_basename, content):
        destination_folder = config.get('EDM', 'server_shared_folder',
            default='/tmp')
        filepath = os.path.join(destination_folder, file_basename)
        with open(filepath, 'wb+') as _file:
            _file.write(content)
        return filepath

    def transition_generate_reports_or_input_parameters(self):
        has_flow_model = False
        has_standard_model = False
        for cur_model in self.select_model.models:
            if cur_model.output_kind == 'flow':
                has_flow_model = True
            elif cur_model.output_kind == 'model':
                has_standard_model = True
            if has_flow_model and has_standard_model:
                Pool().get('report.template').raise_user_error('output_mixin')

        if any([x.parameters for x in self.select_model.models]):
            return 'input_parameters'
        return 'generate_reports'

    def finalize_reports(self, reports, printable_inst):
        if not reports or reports[0]['template'].output_kind != 'flow':
            return super(ReportCreate, self).finalize_reports(
                reports, printable_inst)
        else:
            self.preview_document.reports = reports
            return 'end'
