# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'ReportTemplate',
    'ReportGenerate',
    ]


class ReportTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'report.template'

    generate_event = fields.Boolean('Generate Event', help='If true, an event'
            ' will be generated each time the report is generated.')

    @staticmethod
    def default_generate_event():
        return False

    @classmethod
    def do_generate_event(cls, data):
        if data['model'] == 'report.data':
            return
        pool = Pool()
        Event = pool.get('event')
        model = pool.get(data['model'])
        report_template = pool.get('report.template')(
            data['doc_template'][0])
        _objects = [model(data['id'])]
        # TODO : cache report_template.generate_event
        if report_template.generate_event:
            Event.notify_events(_objects, 'generate_report',
                report_template.name)


class ReportGenerate:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate'

    @classmethod
    def execute(cls, ids, data):
        result = super(ReportGenerate, cls).execute(ids, data)
        report_template = Pool().get('report.template')
        report_template.do_generate_event(data)
        return result


class ReportGenerateFromFile:
    __metaclass__ = PoolMeta
    __name__ = 'report.generate_from_file'

    @classmethod
    def execute(cls, ids, data):
        result = super(ReportGenerateFromFile, cls).execute(ids, data)
        report_template = Pool().get('report.template')
        report_template.do_generate_event(data)
        return result
