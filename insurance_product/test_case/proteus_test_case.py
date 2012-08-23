#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from decimal import Decimal
from proteus import Model


def launch_test_case(cfg_dict):
    Product = Model.get('ins_product.product')
    coverage = Model.get('ins_product.coverage')
    brm = Model.get('ins_product.business_rule_manager')
    gbr = Model.get('ins_product.generic_business_rule')
    pricing = Model.get('ins_product.pricing_rule')

    gbr_a = gbr()
    gbr_a.kind = 'ins_product.pricing_rule'
    gbr_a.start_date = datetime.date.today()
    gbr_a.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_a = gbr_a.pricing_rule[0]
    prm_a.price = Decimal(12.0)
    prm_a.per_sub_elem_price = Decimal(1.0)

    gbr_b = gbr()
    gbr_b.kind = 'ins_product.pricing_rule'
    gbr_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=11)
    gbr_b.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=20)
    prm_b = gbr_b.pricing_rule[0]
    prm_b.price = Decimal(15.0)

    brm_a = brm()
    brm_a.business_rules.append(gbr_a)
    brm_a.business_rules.append(gbr_b)

    coverage_a = coverage()
    coverage_a.code = 'ALP'
    coverage_a.name = 'Alpha Coverage'
    coverage_a.start_date = datetime.date.today()

    gbr_c = gbr()
    gbr_c.kind = 'ins_product.pricing_rule'
    gbr_c.start_date = datetime.date.today()
    gbr_c.end_date = datetime.date.today() + \
                                    datetime.timedelta(days=10)
    prm_c = gbr_c.pricing_rule[0]
    prm_c.price = Decimal(30.0)

    brm_b = brm()
    brm_b.business_rules.append(gbr_c)

    brm_b.save()
    brm_a.save()

    coverage_b = coverage()
    coverage_b.code = 'BET'
    coverage_b.name = 'Beta Coverage'
    coverage_b.start_date = datetime.date.today() + \
                                    datetime.timedelta(days=5)

#    coverage_b.pricing_mgr = []
    coverage_b.pricing_mgr.append(brm_b)

    coverage_a.pricing_mgr.append(brm_a)

    coverage_a.save()
    coverage_b.save()

    product_a = Product()
    product_a.code = 'AAA'
    product_a.name = 'Awesome Alternative Allowance'
    product_a.start_date = datetime.date.today()
    product_a.options.append(coverage_a)
    product_a.options.append(coverage_b)
    product_a.save()
