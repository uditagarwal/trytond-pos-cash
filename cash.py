#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from decimal import Decimal
from receipt import Receipt
import serial
from escpos import escpos

from trytond.model import ModelSQL, ModelView, ModelStorage, ModelSingleton, fields
from trytond.wizard import Wizard
from trytond.pyson import Eval, Equal, Not, Bool, Get
from trytond.pool import Pool

class PosCashConfiguration(ModelSingleton, ModelSQL, ModelView):
    _name = 'pos_cash.configuration'

    sequence = fields.Many2One('ir.sequence.strict', 'Sequence', help='Receipt '
            'number Sequence', required=True)
    printer_port = fields.Char(string='Printer port', help='Port type the '
            'receipt printer is conntected to.')
    display_port = fields.Char('Display port', help='Like /dev/ttyS0')
    display_baud = fields.Numeric('BAUD-Rate', digits=(10,0))
    display_digits = fields.Numeric('Digits per row', digits=(10,0))
    company = fields.Many2One('company.company', 'Company')
    logo = fields.Binary('Receipt Logo')

    def __init__(self):
        super(PosCashConfiguration, self).__init__()
        self._rpc.update({
            'test_printer': True,
            'test_display': True,
        })

    def default_printer_port(self):
        return '/dev/lp0'

    def default_display_port(self):
        return '/dev/ttyS0'

    def default_display_baud(self):
        return 9600

    def test_printer(self, ids):
        receipt = Pool().get('pos_cash.receipt', 'report')
        receipt.test_printer()

    def test_display(self, ids):
        config = self.browse(1)
        port = serial.Serial(config.display_port, config.display_baud)
        display = escpos.Display(port)
        display.set_cursor(False)
        display.clear()
        display.text('Display works!!!\nWell...')
        del display
        port.close()

PosCashConfiguration()


class PosCashSale(ModelSQL, ModelView):
    _name = 'pos_cash.sale'

    receipt_code = fields.Char('Receipt code', readonly=True)
    lines = fields.One2Many('pos_cash.sale.line', 'sale', 'Sale lines')
    cash_received = fields.Numeric('Cash received')
    taxes = fields.Function(fields.One2Many('account.tax', None, 'Taxes'),
            'get_taxes')
    total_amount = fields.Function(fields.Numeric('Total amount', readonly=True),
            'get_total_amount')
    total_tax = fields.Function(fields.Numeric('Total tax'), 'get_total_tax')
    total_without_tax = fields.Function(fields.Numeric('Without tax'),
            'get_without_tax')
    total_paid = fields.Numeric('Total paid', readonly=True)
    drawback = fields.Function(fields.Numeric('Drawback'), 'get_drawback')

    def __init__(self):
        super(PosCashSale, self).__init__()
        self._display = False

    def default_receipt_code(self):
        config_obj = Pool().get('pos_cash.configuration')
        config = config_obj.browse(1)
        sequence_obj = Pool().get('ir.sequence.strict')
        seq_code = sequence_obj.get_id(config.sequence.id)
        res = '%04d%s' % (config.company.id, seq_code)
        return res

    def get_total_amount(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            total = Decimal(0)
            for line in sale.lines:
                total += line.quantity * line.unit_price
            res[sale.id] = total
        return res

    def get_taxes(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            taxes = []
            for line in sale.lines:
                for tax in line.product.customer_taxes_used:
                    if tax.id not in taxes:
                        taxes.append(tax.id)
            res[sale.id] = taxes
        return res

    def get_total_tax(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            res[sale.id] = sale.total_amount-sale.total_without_tax
        return res

    def get_without_tax(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            amount = Decimal(0)
            for line in sale.lines:
                amount += line.without_tax
            res[sale.id] = amount
        return res


    def add_product(self, sale, product, unit_price, qty):
        sale_line_obj = Pool().get('pos_cash.sale.line')
        line_id = sale_line_obj.create({'sale': sale.id,
                    'product': product.id,
                    'unit_price': unit_price,
                    'quantity': qty,
                })
        if not self._display:
           self._display = Pool().get('pos_cash.display', 'report')
        line = sale_line_obj.browse(line_id)
        self._display.show_sale_line(line)

    def cash(self, sale, cash_amount):
        self.write(sale.id, {'total_paid': cash_amount})
        pool = Pool()
        config = pool.get('pos_cash.configuration').browse(1)
        receipt = pool.get('pos_cash.receipt', 'report')
        display = Pool().get('pos_cash.display', 'report')
        display.show_paid(sale)
        receipt.print_sale(sale)

    def get_drawback(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            if sale.total_paid == Decimal(0):
                res[sale.id] = Decimal(0)
            else:
                res[sale.id] = sale.total_paid - sale.total_amount
        return res

PosCashSale()


class PosCashSaleLine(ModelSQL, ModelView):
    _name = 'pos_cash.sale.line'

    sale = fields.Many2One('pos_cash.sale', 'POS Sale', required=True)
    product = fields.Many2One('product.product', 'Product', required=True)
    unit_price = fields.Numeric('Unit price', digits=(16, 2), required=True)
    total = fields.Function(fields.Numeric('Total'), 'get_total')
    quantity = fields.Numeric('Quantity', required=True)
    without_tax = fields.Function(fields.Numeric('Without Tax'),
            'get_without_tax')

    def get_without_tax(self, ids, name):
        res = {}
        for line in self.browse(ids):
            taxes = Decimal(0)
            for tax in line.product.customer_taxes_used:
                taxes += tax.percentage

            res[line.id] = line.total / ((taxes/100)+1)
        return res

    def get_total(self, ids, name):
        res = {}
        for line in self.browse(ids):
            res[line.id] = line.unit_price * line.quantity
        return res

PosCashSaleLine()




