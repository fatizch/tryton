from celery.utils.log import get_task_logger

from trytond.pool import Pool

from batch import BatchRoot

__all__ = [
    'ViewValidationBatch',
    ]

logger = get_task_logger(__name__)


class ViewValidationBatch(BatchRoot):
    'View validation batch'

    __name__ = 'ir.ui.view.validate'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_search_model(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_domain(cls, treatment_date):
        Module = Pool().get('ir.module.module')
        modules = Module.search([])
        utils_module = Module.search([('name', '=', 'cog_utils')])[0]
        coop_modules = set([module.name for module in modules
                if utils_module in module.parents])
        return [('module', 'in', coop_modules)]

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        for view in objects:
            try:
                full_xml_id = view.xml_id
                if full_xml_id == '':
                    continue
                xml_id = full_xml_id.split('.')[-1]
                if view.inherit:
                    full_inherited_xml_id = view.inherit.xml_id
                    if full_inherited_xml_id.split('.')[-1] != xml_id:
                        logger.warning('View %s inherits from %s but has '
                            'different id !' % (full_xml_id,
                                full_inherited_xml_id))
            except:
                logger.error('Failed testing view %s' % view.id)
                raise
