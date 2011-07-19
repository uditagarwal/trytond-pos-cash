#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement

from receipt import Receipt

from trytond.model import ModelSQL, ModelView, ModelStorage, ModelSingleton, fields
from trytond.wizard import Wizard
from trytond.pyson import Eval, Equal, Not, Bool, Get
from trytond.pool import Pool

class PosCashConfiguration(ModelSingleton, ModelSQL, ModelView):
    _name = 'pos_cash.configuration'

    printer_port = fields.Char(string='Printer port', help='Port type the '
            'receipt printer is conntected to.')
    company = fields.Many2One('company.company', 'Company')
    logo = fields.Binary('Receipt Logo')

    def __init__(self):
        super(PosCashConfiguration, self).__init__()
        self._rpc.update({
            'test_printer': True,
        })

    def default_printer_port(self):
        return '/dev/lp0'

    def test_printer(self, ids):
        config = self.browse(ids[0])
        receipt = Receipt(config)
        receipt.test_printer()

PosCashConfiguration()


class PosCashSale(ModelSQL, ModelView):
    _name = 'pos_cash.sale'

    lines = fields.One2Many('pos_cash.sale.line', 'sale', 'Sale lines')
    cash_received = fields.Numeric('Cash received')
    taxes = fields.Function(fields.One2Many('account.tax', None, 'Taxes'),
            'get_taxes')

    def get_taxes(self, ids, name):
        print 'get_taxes'
        res = {}
        for sale in self.browse(ids):
            taxes = []
            for line in sale.lines:
                for tax in line.product.customer_taxes_used:
                    if tax.id not in taxes:
                        taxes.append(tax.id)
            res[sale.id] = taxes

        return res

    def add_product(self, sale, product, qty):
        sale_line_obj = Pool().get('pos_cash.sale.line')
        sale_line_obj.create({'sale': sale.id,
                    'product': product,
                    'quantity': qty,
                })

PosCashSale()


class PosCashSaleLine(ModelSQL, ModelView):
    _name = 'pos_cash.sale.line'

    sale = fields.Many2One('pos_cash.sale', 'POS Sale', required='True')
    product = fields.Many2One('product.product', 'Product', required='True')
    name = fields.Function(fields.Char('Name'), 'get_name')
    unit_price = fields.Numeric('Unit price', required='True')
    quantity = fields.Numeric('Quantity', required='True')

PosCashSaleLine()




