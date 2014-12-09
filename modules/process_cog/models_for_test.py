from trytond.modules.cog_utils import model
from trytond.modules.process_cog import CogProcessFramework

__all__ = [
    'ModelProcess'
    ]


class ModelProcess(model.CoopSQL, CogProcessFramework):
    'Test Model Process'
    __name__ = 'process.test.model'
