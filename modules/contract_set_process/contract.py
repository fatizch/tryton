from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    ]


class ContractSet(CogProcessFramework):
    __name__ = 'contract.set'
    __metaclass__ = ClassAttr

    covered_parties = fields.Function(
        fields.One2Many('party.party', None, 'Covered Parties'),
        'get_covered_parties')
    party_relations = fields.Function(
        fields.One2Many('party.relation.all', None, 'Party Relations',
            depends=['covered_parties'],
            domain=['OR',
                [('from_', 'in', Eval('covered_parties'))],
                [('to', 'in', Eval('covered_parties'))]
                ]),
        'get_party_relations', setter='set_party_relations')
    attachments = fields.Function(
        fields.One2Many('ir.attachment', 'resource', 'Contracts Attachments'),
        'get_attachments')
    contracts_processes_over = fields.Function(
        fields.Boolean('All Processes On Contracts Are Over', readonly=True),
        'getter_contracts_processes_over')

    def getter_contracts_processes_over(self, name):
        return all([not x.current_state for x in self.contracts])

    def get_party_relations(self, name):
        parties = []
        for contract in self.contracts:
            parties.extend(covered.party for covered in
                contract.covered_elements)
        parties = list(set(parties))
        return [relation.id for party in parties
            for relation in party.relations]

    @classmethod
    def set_party_relations(cls, objects, name, values):
        pool = Pool()
        relation = pool.get('party.relation.all')
        res = []
        for value in values:
            if value[0] == 'create':
                res.extend(value[1])
        if res:
            return relation.create(res)
        else:
            return []

    def get_covered_parties(self, name):
        parties = []
        for contract in self.contracts:
            parties.extend(covered.party for covered in
                contract.covered_elements)
        parties = list(set(parties))
        res = [party.id for party in parties]
        return res

    def generate_and_attach_reports_on_set(self, template_codes):
            """template_codes should be a comma separated list
            of document template codes between single quotes,
            i.e : 'template1', 'template2', etc.
            """
            pool = Pool()
            Template = pool.get('document.template')
            Attachment = pool.get('ir.attachment')
            Report = pool.get('document.generate.report', type='report')
            Date = pool.get('ir.date')

            template_instances = Template.search([('code', 'in',
                        template_codes), ('internal_edm', '=', 'True')])

            for template_instance in template_instances:
                _, filedata, _, file_basename = Report.execute(
                    [self.id], {
                            'id': self.id,
                            'ids': [self.id],
                            'model': 'contract.set',
                            'doc_template': [template_instance],
                            'party': self.contracts[0].subscriber.id,
                            'address': (
                                self.contracts[0].subscriber.addresses[0].id),
                            'sender': None,
                            'sender_address': None,
                            })
            data = Report.unoconv(filedata, 'odt', 'pdf')

            attachment = Attachment()
            attachment.resource = 'contract.set,%s' % self.id
            attachment.data = data
            date_string = Date.date_as_string(utils.today(),
                    self.contracts[0].company.party.lang)
            date_string_underscore = ''.join([c if c.isdigit() else "_"
                    for c in date_string])
            attachment.name = '%s_%s_%s.pdf' % (template_instance.name,
                self.rec_name, date_string_underscore)
            attachment.document_desc = template_instance.document_desc
            attachment.save()

    def get_attachments(self, name):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        attachments = []

        operand = ['%s,%s' % (contract.__name__, contract.id)
            for contract in self.contracts]
        operand.append('%s,%s' % (self.__name__, self.id))

        attachments.extend([x.id for x in Attachment.search(
                [('resource', 'in', operand)])])

        return attachments
