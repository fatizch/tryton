from trytond.modules.process_cog import CogProcessFramework

__all__ = [
    'ModelProcess'
    ]


class ModelProcess(CogProcessFramework):
    'Test Model Process'
    __name__ = 'process.test.model'
