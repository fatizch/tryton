from trytond.pool import PoolMeta

MODULE_NAME = 'life_claim'

__all__ = [
    'TestCaseModel',
]

__metaclass__ = PoolMeta


class TestCaseModel:
    'Test Case Model'

    __name__ = 'ir.test_case'

    @classmethod
    def document_desc_test_case(cls):
        documents = super(TestCaseModel, cls).document_desc_test_case()
        translater = cls.get_translater(MODULE_NAME)
        documents.append(cls.create_document('WI', translater(
                    'Work Incapacity')))
        documents.append(cls.create_document('DH', translater(
                    'Death Certificate')))
        documents.append(cls.create_document('AT', translater(
                    'Amortization Table')))
        documents.append(cls.create_document('DY', translater(
                    'Disability Justification')))
        return documents

    @classmethod
    def event_desc_test_case(cls):
        event_descs = super(TestCaseModel, cls).event_desc_test_case()
        translater = cls.get_translater(MODULE_NAME)
        event_descs.append(cls.create_event_desc('DI', translater('Disease')))
        event_descs.append(cls.create_event_desc('AC', translater('Accident')))
        return event_descs

    @classmethod
    def loss_desc_test_case(cls):
        loss_descs = super(TestCaseModel, cls).loss_desc_test_case()
        translater = cls.get_translater(MODULE_NAME)
        loss_descs.append(cls.create_loss_desc('WI', translater(
                    'Work Incapacity'), 'person', True, ['AC'], ['WI']))
        loss_descs.append(cls.create_loss_desc('DH', translater('Death'),
                'person', False, ['AC', 'DI'], ['DH']))
        loss_descs.append(cls.create_loss_desc('DY', translater('Disability'),
                'person', False, ['AC', 'DI'], ['WI']))
        return loss_descs
