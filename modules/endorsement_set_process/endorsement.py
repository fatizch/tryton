# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.process_cog.process import CoogProcessFramework
from trytond.modules.process import ClassAttr
from trytond.modules.coog_core import fields, model
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = [
    'Endorsement',
    'EndorsementPartUnion',
    'EndorsementSet',
    ]


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    generated_sets_processes_over = fields.Function(
        fields.Boolean('All Processes On Generated Endorsement Sets Are Over'),
        'get_generated_sets_processes_over')

    @classmethod
    def endorse_contracts(cls, contracts, endorsement_definition, origin=None):
        pool = Pool()
        Process = pool.get('process')
        EndorsementSet = pool.get('endorsement.set')
        endorsements = super(Endorsement, cls).endorse_contracts(
            contracts, endorsement_definition, origin)
        endorsement_sets = list(set([x.endorsement_set for x in endorsements if
            hasattr(x, 'endorsement_set') and x.endorsement_set]))
        processes = Process.search([('on_model.model', '=',
                    'endorsement.set')])
        if processes:
            process = processes[0]
            state = process.first_step()
            for end_set in endorsement_sets:
                end_set.current_state = state
            EndorsementSet.save(endorsement_sets)
        for endorsement in endorsements:
            endorsement.current_state = None
        cls.save(endorsements)
        return endorsements

    def get_generated_sets_processes_over(self, name):
        return all([not x.current_state for x in
                self.generated_endorsement_sets])


class EndorsementSet(CoogProcessFramework):

    __name__ = 'endorsement.set'
    __metaclass__ = ClassAttr

    endorsements_parts_union = fields.Function(
        fields.One2Many('endorsement.part.union',
            None, 'Endorsement Parts',
            context={'endorsement_set': Eval('id')},
            depends=['id']),
        'get_endorsements_parts_union', setter='setter_void')
    created_attachments = fields.Function(
        fields.One2Many('ir.attachment', 'origin',
            'Created Attachments'), 'get_created_attachments')
    attachments = fields.One2Many('ir.attachment', 'resource',
        'Attachments', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementSet, cls).__setup__()
        cls._error_messages.update({
                'no_effective_date': 'Effective date is not defined',
                })
        cls._buttons.update({
                'button_resume_process': {},
                })

    @classmethod
    def _export_skips(cls):
        return super(EndorsementSet, cls)._export_skips() | {'attachments'}

    @classmethod
    @model.CoogView.button_action('process_cog.act_resume_process')
    def button_resume_process(cls, endorsement_sets):
        pass

    def check_endorsements_effective_date(self):
        if not self.effective_date:
            self.append_functional_error('no_effective_date')

    def get_endorsements_parts_union(self, name):
        # See table_query method on EndorsementPartUnion
        # in endorsement_process/endorsement.py
        res = []
        for endorsement in self.endorsements:
            for part in endorsement.definition.endorsement_parts:
                res.append(part.id + 100 * endorsement.id)
        return res

    def get_created_attachments(self, name):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        endorsements = ['%s,%s' % (endorsement.__name__, endorsement.id)
            for endorsement in self.endorsements]
        endorsements_and_set = endorsements + ['endorsement.set,%s' % self.id]

        return [x.id for x in Attachment.search(
            ['OR', [('resource', 'in', endorsements)],
                [('origin', 'in', endorsements_and_set)]])]


class EndorsementPartUnion:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.part.union'

    @classmethod
    def table_query(cls):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        ctx_endorsement_set = Transaction().context.get('endorsement_set',
            None)
        if ctx_endorsement_set:
            good_set = EndorsementSet(ctx_endorsement_set)
            good_endorsements = [x.id for x in good_set.endorsements]
            with Transaction().set_context({'endorsement': good_endorsements}):
                return super(EndorsementPartUnion, cls).table_query()
        else:
            return super(EndorsementPartUnion, cls).table_query()
