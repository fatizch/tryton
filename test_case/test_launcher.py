#!/usr/bin/python
# -*- coding: utf-8 -*-

from product_test_case import main
import os


DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..')))
os.remove(os.path.join(DIR, 'data/Test.sqlite'))
main(
    'Test',
    ['insurance_contract'],
    'admin',
    'admin',
    os.path.join(DIR, 'conf/trytond.conf'))
