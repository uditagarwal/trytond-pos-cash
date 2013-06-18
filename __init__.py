# -*- coding: utf-8 -*-
"""
    __init__

    pos_cash

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool

from cash import PosCashConfiguration, PosCashSale, PosCashSaleLine
from wizards import AddProductSelect, WizardAddProduct, CashAmountEnter, \
    WizardCashSale
from reporting import Receipt, Display
from product import Template

def register():
    "Register classes"
    Pool.register(
        PosCashConfiguration,
        PosCashSale,
        PosCashSaleLine,
        AddProductSelect,
        WizardAddProduct,
        CashAmountEnter,
        WizardCashSale,
        Receipt,
        Display,
        Template,
        module='pos_cash_label', type_='model'
    )
