# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model
from trytond.modules.process_cog import ProcessFinder, ProcessStart


__all__ = [
    'Process',
    'UnderwritingStart',
    'ProcessUnderwritingType',
    'UnderwritingStartFindProcess',
    ]


class Process:
    __metaclass__ = PoolMeta
    __name__ = 'process'

    underwriting_types = fields.Many2Many('process-underwriting.type',
        'process', 'underwriting_type', 'Underwriting Types',
        states={'invisible': Eval('kind') != 'underwriting'},
        depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('underwriting', 'Underwriting Creation'))

    @classmethod
    def _export_skips(cls):
        return (super(Process, cls)._export_skips() | set(
                ['underwriting_types']))


class ProcessUnderwritingType(model.CoogSQL):
    'Process Underwriting Type Relation'

    __name__ = 'process-underwriting.type'

    underwriting_type = fields.Many2One('underwriting.type',
        'Underwriting Type', ondelete='CASCADE', required=True, select=True)
    process = fields.Many2One('process', 'Process', ondelete='CASCADE',
        required=True, select=True)


class UnderwritingStart(ProcessFinder):
    'Underwriting Start'

    __name__ = 'underwriting.start'

    @classmethod
    def default_model(cls):
        Start = Pool().get(cls.get_parameters_model())
        defaults = super(UnderwritingStart, cls).default_model()
        models = {x[0] for x in Start.selection_parent()}
        active_model = Transaction().context.get('active_model', None)
        active_id = Transaction().context.get('active_id', None)
        if active_model == 'party.party':
            defaults['party'] = active_id
        if active_model in models:
            defaults['parent'] = '%s,%s' % (active_model, active_id)
        return defaults

    @classmethod
    def get_parameters_model(cls):
        return 'underwriting.start.find_process'

    @classmethod
    def get_parameters_view(cls):
        return 'underwriting_process.underwriting_start_find_process_view_form'

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(UnderwritingStart,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.type_ = process_param.underwriting_type
            if process_param.party:
                obj.party = process_param.party
            if process_param.parent:
                obj.on_object = process_param.parent
        return res, errs


class UnderwritingStartFindProcess(ProcessStart):
    'Underwriting Process - Find Process'

    __name__ = 'underwriting.start.find_process'

    party = fields.Many2One('party.party', 'Party')
    underwriting_type = fields.Many2One('underwriting.type', 'Type',
        required=True)
    parent = fields.Reference('For Object', 'selection_parent')

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'underwriting')])[0].id

    @fields.depends('underwriting_type')
    def on_change_with_good_process(self):
        return super(UnderwritingStartFindProcess,
            self).on_change_with_good_process()

    @classmethod
    def selection_parent(cls):
        pool = Pool()
        Underwriting = pool.get('underwriting')
        Model = pool.get('ir.model')
        selection = Underwriting.on_object.selection
        models = Model.search([('model', 'in', [x[0] for x in selection])])
        return sorted([(x.model, x.name) for x in models],
            key=lambda x: x[1])

    @classmethod
    def build_process_domain(cls):
        result = super(
            UnderwritingStartFindProcess, cls).build_process_domain()
        result.append(('kind', '=', 'underwriting'))
        result.append(('underwriting_types', '=', Eval('underwriting_type')))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            UnderwritingStartFindProcess, cls).build_process_depends()
        result.append('underwriting_type')
        return result
