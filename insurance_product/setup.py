from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='insurance_product',
      version=version,
      description="Coopengo insurance product  classes for Tryton",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='tryton coopengo workflow business classes insurance product',
      author='',
      author_email='',
      url='',
      license='',   
      package_dir={'trytond.modules.insurance_product': '.',},
      packages=['trytond.modules.insurance_product',],
      package_data={'trytond.modules.insurance_product':['*.py','*.xml','*.pyc'],},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      [trytond.modules]
      insurance_product = trytond.modules.insurance_product
      """,
      )
