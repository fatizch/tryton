from trytond.pool import PoolMeta, Pool

MODULE_NAME = 'claim_life'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def document_desc_test_case(cls):
        Document = Pool().get('document.description')
        super(TestCaseModel, cls).document_desc_test_case()
        translater = cls.get_translater(MODULE_NAME)
        documents = []
        documents.append(cls.create_document(code='WI', name=translater(
                    'Work Incapacity')))
        documents.append(cls.create_document(code='DH', name=translater(
                    'Death Certificate')))
        documents.append(cls.create_document(code='DY', name=translater(
                    'Disability Justification')))
        Document.create([x._save_values for x in documents])

    @classmethod
    def event_desc_test_case(cls):
        EventDesc = Pool().get('benefit.event.description')
        super(TestCaseModel, cls).event_desc_test_case()
        event_descs = []
        translater = cls.get_translater(MODULE_NAME)
        event_descs.append(cls.create_event_desc(code='DI',
                name=translater('Disease')))
        event_descs.append(cls.create_event_desc(code='AC',
                name=translater('Accident')))
        EventDesc.create([x._save_values for x in event_descs])

    @classmethod
    def loss_desc_test_case(cls):
        LossDesc = Pool().get('benefit.loss.description')
        super(TestCaseModel, cls).loss_desc_test_case()
        translater = cls.get_translater(MODULE_NAME)
        loss_descs = []
        loss_descs.append(cls.create_loss_desc(code='WI',
                name=translater('Work Incapacity'),
                item_kind='person', with_end_date=True,
                event_descs=[cls.get_event_desc('AC')],
                documents=[cls.get_document_desc('WI')]))
        loss_descs.append(cls.create_loss_desc(code='DH',
                name=translater('Death'),
                item_kind='person', with_end_date=False,
                event_descs=[cls.get_event_desc('AC'),
                    cls.get_event_desc('DI')],
                documents=[cls.get_document_desc('DH')]))
        loss_descs.append(cls.create_loss_desc(code='DY',
                name=translater('Disability'),
                item_kind='person', with_end_date=False,
                event_descs=[cls.get_event_desc('AC'),
                    cls.get_event_desc('DI')],
                documents=[cls.get_document_desc('WI')]))
        LossDesc.create([x._save_values for x in loss_descs])
