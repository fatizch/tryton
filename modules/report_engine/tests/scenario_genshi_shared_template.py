# #Comment# #Imports
import datetime
import os
import tempfile
import shutil
from proteus import Model, Wizard

from trytond.tests.tools import activate_modules
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.currency.tests.tools import get_currency

from trytond.modules.report_engine import batch as report_engine

# #Comment# #Install Modules
config = activate_modules(['report_engine', 'offered'])
module_file = report_engine.__file__
module_folder = os.path.dirname(module_file)

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)
version_start_date = datetime.date(2014, 1, 1)

# #Comment# #Get Models
IrModel = Model.get('ir.model')
ReportTemplate = Model.get('report.template')
ReportTemplateVersion = Model.get('report.template.version')
ReportSharedTemplate = Model.get('report.shared_template')
Lang = Model.get('ir.lang')

product_model, = IrModel.find(['model', '=', 'offered.product'])

temp_dir = tempfile.gettempdir()
# Create report template
report_template = ReportTemplate()
report_template.name = 'Test genshi'
report_template.code = 'test_genshi'
report_template.on_model = product_model
report_template.input_kind = 'shared_genshi_template'
report_template.save()

# Create Shared Template
shared_template = ReportSharedTemplate()
shared_template.name = 'Test genshi'
shared_template.code = 'test_genshi'
file_path = os.path.join(module_folder, 'tests_imports/') + 'test.xml'
with open(file_path, 'rb') as f:
    shared_template.data = f.read()
shared_template.save()
# Create Version
version = ReportTemplateVersion()
version.is_shared_template = True
version.template = report_template
version.start_date = version_start_date
version.shared_template = shared_template
version.language, = Lang.find([('code', '=', 'fr')])
version.save()

# Create product
# #Comment# #Create currenct
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
product = init_product()
product.save()
# Wizard

createReport = Wizard('report.create', models=[product])
createReport.form.template = report_template
createReport.execute('generate')
expectation = False
for root, dirs, files in os.walk(tempfile.gettempdir()):
    if files and 'Test_genshi-Test_Product-' in files[0]:
        dir = root
        path = root + '/' + files[0]
        expectation = True

expectation
# #Res# #True
with open(path) as f:
    lines = f.readlines()

shutil.rmtree(dir)

'<p>%s</p>' % product.id in lines[2]
# #Res# #True
'<p>Dunder Mifflin</p>' == lines[-2].strip()
# #Res# #True
'<p>%s</p>' % product.rec_name == lines[-1].strip()
# #Res# #True
