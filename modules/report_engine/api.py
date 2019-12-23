# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
from itertools import groupby

from trytond.pool import Pool
from trytond.model.exceptions import AccessError
from trytond.modules.coog_core import api
from trytond.modules.api import APIMixin, APIInputError
from . import report_engine

REPORT_DATA_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'data': {'type': 'object'},
        },
    'required': ['data'],
    }


class APIReport(APIMixin):
    'API Report'
    __name__ = 'api.report'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'generate_documents': {
                    'public': False,
                    'readonly': False,
                    'description': cls.generate_documents.__doc__,
                    },
                'get_document': {
                    'public': False,
                    'readonly': True,
                    'description': 'Get a document by edm_id'
                    }
                })

    @classmethod
    def generate_documents(cls, parameters):
        """Generate the reports matching the document desc.

        If the objects in data are not records of a model
        known to Coog, their model key must be report.data,
        and the filters parameter is required.

        """
        pool = Pool()

        records = parameters['records']
        document_descs = parameters['documents']
        filters = parameters['filters']

        EventTypeAction = pool.get('event.type.action')
        reports = []
        # In case filters are provided, we assume
        # they have a report_templates field
        for record in records:
            if not filters:
                templates = EventTypeAction.get_templates_list(record)
            else:
                templates = sum(
                    [list(getattr(filter_, 'report_templates', []))
                        for filter_ in filters],
                    [])
            filtered_templates = [x for x in templates
                if x.document_desc in document_descs]
            for template in filtered_templates:
                reports.append(cls._api_generate_report(template, record))
        return {'documents': [{'edm_id': report['edm_id']}
                for report in reports]}

    @classmethod
    def _api_generate_report(cls, template, record):
        ctx = {}
        if isinstance(record, report_engine.ReportData):
            ctx.update({'records': [record], 'resource': template})
        report = template._generate_report([record], ctx)
        if template.format_for_internal_edm:
            if isinstance(record, report_engine.ReportData):
                report['resource'] = template
                report['origin'] = None
            template.save_reports_in_edm([report])
        return report

    @classmethod
    def _generate_documents_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')

        parameters['records'] = cls._json_to_records(parameters['records'])

        document_descs = [API.instantiate_code_object('document.description',
            coded) for coded in parameters['documents']]
        parameters['documents'] = document_descs

        if parameters.get('filters'):
            parameters['filters'] = cls._json_to_records(parameters['filters'])
        else:
            parameters['filters'] = []

        if not parameters['filters']:
            if any(isinstance(record, report_engine.ReportData)
                    for record in parameters['records']):
                raise APIInputError({'type': 'report_data_filters_required'})

        return parameters

    @classmethod
    def _generate_documents_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'records': {
                    'type': 'array',
                    'items': {
                        'anyOf': [
                            api.TECHNICAL_RECORD_SCHEMA,
                            REPORT_DATA_SCHEMA,
                            ]
                    }
                },
                'documents': api.CODED_OBJECT_ARRAY_SCHEMA,
                'filters': api.TECHNICAL_RECORD_ARRAY_SCHEMA,
                },
            'required': ['records', 'documents'],
            }

    @classmethod
    def _generate_documents_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'documents': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'edm_id': api.CODE_SCHEMA,
                            },
                        'required': ['edm_id'],
                        },
                    },
                },
            'required': ['documents'],
        }

    @classmethod
    def _generate_documents_examples(cls):
        return [
            {
                'input': {
                    'records': [
                        {
                            'data': {'talk': 'quack'},
                        }
                    ],
                    'documents': [{'code': 'tester'}],
                    'filters': [{'model': 'event.type.action', 'id': 12}]
                },
                'output': {'documents': [{'edm_id': '1'}]}
            }
        ]

    @classmethod
    def _json_to_records(cls, json_records):

        """
        Instantiate a list of dicts that conforms to either:
            - api.TECHNICAL_RECORD_SCHEMA,
            - REPORT_DATA_SCHEMA,
        """

        pool = Pool()
        ReportData = report_engine.ReportData

        def keyfunc(x):
            return x.get('model', '')

        json_records = sorted(json_records, key=keyfunc)
        records = []
        for model_, grouped_records in groupby(json_records, key=keyfunc):
            if not model_:
                group = [ReportData(record['data'])
                    for record in grouped_records]
            else:
                group = pool.get(model_).browse([record['id']
                        for record in grouped_records])
            records.extend(group)
        return records

    @classmethod
    def get_document(cls, parameters):
        id_ = parameters['edm_id']
        data = cls._get_document_data(id_)
        return {'edm_id': id_, 'data': data}

    def _get_document_data(id_):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        try:
            data = Attachment(int(id_)).data
        except AccessError:
            raise APIInputError([{'type': 'wrong_edm_id'}])
        return base64.b64encode(data).decode()

    @classmethod
    def _get_document_convert_input(cls, parameters):
        return parameters

    @classmethod
    def _get_document_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'edm_id': {'type': 'string'}
                },
            'required': ['edm_id'],
            }

    @classmethod
    def _get_document_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'edm_id': {'type': 'string'},
                'data': {'type': 'string'}
                },
            'required': ['edm_id'],
            }

    @classmethod
    def _get_document_examples(cls):
        return [
            {
                'input': {
                    'edm_id': '123',
                },
                'output': {'edm_id': '123', 'data': 'Ym9uam91cgo=='}
            }
        ]
