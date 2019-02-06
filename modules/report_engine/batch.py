# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import datetime

from decimal import Decimal
from sql import Literal, Null
from itertools import groupby

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch


__all__ = [
    'ReportProductionRequestTreatmentBatch',
    'GenerateReportPeriod',
    ]


class ReportProductionRequestTreatmentBatch(batch.BatchRoot):
    'Report Production Request Treatment Batch'

    __name__ = 'report_production.request.batch_treat'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(ReportProductionRequestTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'report_production.request'

    @classmethod
    def select_ids(cls):
        cursor = Transaction().connection.cursor()
        ProductionRequest = Pool().get('report_production.request')
        main_table = ProductionRequest.__table__()
        query = main_table.select(main_table.report_template, main_table.id,
            where=(main_table.treated == Literal(False) &
                (main_table.report_template != Literal(Null))),
            order_by=[main_table.report_template])
        cursor.execute(*query)
        records = [(tmpl, req) for tmpl, req in cursor.fetchall()]
        selected = []
        for template, requests in groupby(records, lambda x:
                x[0]):
            selected.append([(x[1],) for x in requests])
        return selected

    @classmethod
    def execute(cls, objects, ids):
        ReportProductionRequest = Pool().get('report_production.request')
        reports, attachments = ReportProductionRequest.treat_requests(objects)
        cls.logger.info('Produced %s reports, and created %s attachments' %
            (len(reports), len(attachments)))


class ReportRequestCreationBatch(batch.BatchRoot):
    'Report Request Creation Batch'

    @classmethod
    def execute(cls, objects, ids, template, **template_args):
        pool = Pool()
        Template = pool.get('report.template')
        Request = pool.get('report_production.request')
        template, = Template.search([('code', '=', template)])
        context = {}
        for param in template.parameters:
            if param.name in template_args:
                key = param.name_in_template
                if param.type_ == 'date':
                    context[key] = datetime.datetime.strptime(
                        template_args[param.name], '%Y-%m-%d').date()
                elif param.type_ == 'boolean':
                    context[key] = template_args[param.name] not in (
                        'False', '0', 'false')
                elif param.type_ == 'integer':
                    context[key] = int(template_args[param.name])
                elif param.type_ == 'numeric':
                    context[key] = Decimal(template_args[param.name])
                else:
                    context[key] = template_args[param.name]
        Request.create_report_production_requests(
            template, objects, context)


class GenerateReportPeriod(batch.BatchRoot):
    'Generate Letter Period'

    __name__ = 'report.generate.period'

    @classmethod
    def parse_params(cls, params):
        params = super(GenerateReportPeriod, cls).parse_params(params)
        assert 'on_model' in params, 'on_model parameter is required'
        assert 'from_date' in params, 'from_date parameter is required'
        assert 'to_date' in params, 'to_date parameter is required'
        assert 'template_code' in params, 'template_code parameter is required'
        params['from_date'] = datetime.datetime.strptime(params['from_date'],
            '%Y-%m-%d').date()
        params['to_date'] = datetime.datetime.strptime(params['to_date'],
            '%Y-%m-%d').date()
        return params

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        MainModel = Pool().get('contract')
        return MainModel.browse([x[0] for x in ids])

    @classmethod
    def _get_tables(cls, **kwargs):
        '''
        Returns a dictionnary with all the tables to use for building the
        select ids query
        '''
        return {
            kwargs['on_model']: Pool().get(kwargs['on_model']).__table__(),
            }

    @classmethod
    def _get_query_table(cls, tables, **kwargs):
        '''
        Returns the pythonSQL query table to use for selection
        '''
        return tables[kwargs['on_model']]

    @classmethod
    def _get_group_by(cls, tables, **kwargs):
        '''
        Returns the group by clause used by the select ids function
        '''
        return []

    @classmethod
    def _get_where_clause(cls, tables, **kwargs):
        '''
        Returns the where clause used by the select ids function
        '''
        return Literal(True)

    @classmethod
    def _get_order_clause(cls, tables, **kwargs):
        '''
        Returns the order clause used by the select ids function
        '''
        return []

    @classmethod
    def _get_select_fields(cls, tables, **kwargs):
        '''
        Returns a tuple of pythonSQL fields to be selected by the select ids
        function
        '''
        return (tables[kwargs['on_model']].id,)

    @classmethod
    def _filter_query_ids(cls, selection, **kwargs):
        '''
        Filters the select ids selection and returns the new list / generator
        expression
        '''
        return [(x,) for x in selection]

    @classmethod
    def select_ids(cls, treatment_date, **kwargs):
        cursor = Transaction().connection.cursor()
        tables = cls._get_tables(**kwargs)
        query_table = cls._get_query_table(tables, **kwargs)
        fields = cls._get_select_fields(tables, **kwargs)
        where_clause = cls._get_where_clause(tables, **kwargs)
        group_by = cls._get_group_by(tables, **kwargs)
        order_clause = cls._get_order_clause(tables, **kwargs)

        cursor.execute(*query_table.select(*fields,
                where=where_clause,
                group_by=group_by,
                order_by=order_clause
                ))

        return cls._filter_query_ids(cursor.fetchall(),
            treatment_date=treatment_date, **kwargs)

    @classmethod
    def execute(cls, objects, ids, treatment_date, on_model, from_date,
            to_date, template_code, **kwargs):
        '''
        Execute method which creates report request to treat with the objects
        using the template code as report template
        '''
        pool = Pool()
        ReportRequest = pool.get('report_production.request')
        Template = pool.get('report.template')
        template, = Template.search([('code', '=', template_code)])
        to_create = []
        for obj in objects:
            to_create.append({
                    'report_template': template,
                    'object_': str(obj),
                    'context_': '{}',
                    })
        ReportRequest.create(to_create)
