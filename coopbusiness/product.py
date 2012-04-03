from trytond.model import ModelView, ModelSQL, fields 

class Coverage(ModelSQL, ModelView):
    'Coverage'     
    _name = 'product.coverage'     
    _description = __doc__     
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)     
	
Coverage()

class ProductOptionsCoverage(ModelSQL):
    'Define Product - Coverage relations'
    _name = 'product-options-coverage'
    product = fields.Many2One('product.product','Product',select=1, required=True)
    coverage = fields.Many2One('product.coverage','Coverage',select=1, required=True)
	
ProductOptionsCoverage()	
	
class Product(ModelSQL, ModelView):
    'Product'     
    _name = 'product.product'     
    _description = __doc__     
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)     
    options = fields.Many2Many('product-options-coverage','product','coverage','Possible Options')
	
Product()