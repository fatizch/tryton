# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model
from trytond.modules.process_cog.process import ProcessFinder, ProcessStart


__all__ = [
    'Process',
    'UnderwritingStart',
    'ProcessUnderwritingType',
    'UnderwritingStartFindProcess',
    'UnderwritingStartFindProcessResult',
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

    def default_process_parameters(self, name):
        Start = Pool().get(self.get_parameters_model())
        defaults = {}
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

    def finalize_main_object(self, underwriting):
        if not self.process_parameters.results:
            return
        results = []
        for result in self.process_parameters.results:
            if not result.selected:
                continue
            results.append(result.new_result(underwriting, self))
        if results:
            underwriting.results = results
            underwriting.save()
        underwriting.create_documents([underwriting])


class UnderwritingStartFindProcess(ProcessStart):
    'Underwriting Process - Find Process'

    __name__ = 'underwriting.start.find_process'

    effective_date = fields.Date('Effective Date')
    party = fields.Many2One('party.party', 'Party')
    underwriting_type = fields.Many2One('underwriting.type', 'Type',
        required=True)
    parent = fields.Reference('For Object', 'selection_parent')
    results = fields.One2Many('underwriting.start.find_process.result', None,
        'Results', readonly=True, states={
            'invisible': ~Eval('parent') | ~Eval('party')})

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'underwriting')])[0].id

    @fields.depends('underwriting_type')
    def on_change_with_good_process(self):
        return super(UnderwritingStartFindProcess,
            self).on_change_with_good_process()

    @fields.depends('parent', 'party')
    def on_change_parent(self):
        pool = Pool()
        Underwriting = pool.get('underwriting')
        Result = pool.get('underwriting.start.find_process.result')
        if not self.party or not self.parent or not self.parent.id >= 0:
            self.results = []
            return

        fake_underwriting = Underwriting(on_object=self.parent,
            party=self.party)
        results = []
        for elem in fake_underwriting.get_possible_result_targets():
            results.append(Result.new_target(elem))
        self.results = results

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


class UnderwritingStartFindProcessResult(model.CoogView):
    'Underwriting Process Possible Result'
    __name__ = 'underwriting.start.find_process.result'

    selected = fields.Boolean('Selected')
    name = fields.Char('Name', readonly=True)
    target = fields.Char('Target', readonly=True)

    @classmethod
    def new_target(cls, target):
        return cls(selected=False, name=target.rec_name, target=str(target))

    def new_result(self, underwriting, wizard):
        result = Pool().get('underwriting.result')()
        result.target = self.target
        result.effective_decision_date = \
            wizard.process_parameters.effective_date
        result.underwriting = underwriting
        result.on_change_underwriting()
        return result
