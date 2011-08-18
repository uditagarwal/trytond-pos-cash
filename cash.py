#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from decimal import Decimal
import serial
from escpos import escpos

from trytond.model import ModelSQL, ModelView, ModelStorage, ModelSingleton, fields
from trytond.wizard import Wizard
from trytond.pyson import If, In, Eval, Get, Or, Not, Equal, Bool, And
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
        configuration_obj = Pool().get('pos_cash.configuration')

        configuration_id = configuration_obj.search([])[0]
        configuration = configuration_obj.browse(configuration_id)

        if configuration.display_port:
            port = serial.Serial(
                configuration.display_port, configuration.display_baud)
            display = escpos.Display(port)
            display.set_cursor(False)
            display.clear()
            display.text('Display works!!!')
            display.new_line()
            display.text('Well!!!')
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
        self._disp = False
        self._rpc.update({
            'add_product': True,
            'add_sum': True,
            'set_quantity': True,
            'cash_sale': True
        })

    @property
    def _display(self):
        if not self._disp:
            self._disp = Pool().get('pos_cash.display', 'report')
        return self._disp

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
                for tax in line.taxes:
                    if tax.id not in taxes:
                        taxes.append(tax.id)
            res[sale.id] = taxes
        return res

    def get_total_tax(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            res[sale.id] = sale.total_amount - sale.total_without_tax
        return res

    def get_without_tax(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            amount = Decimal(0)
            for line in sale.lines:
                amount += line.without_tax
            res[sale.id] = amount
        return res


    def add_product(self, sale, product, qty, unit_price=None):
        pool = Pool()
        product_obj = pool.get('product.product')
        configuration_obj = pool.get('pos_cash.configuration')
        sale_line_obj = pool.get('pos_cash.sale.line')

        product = product_obj.browse(product)
        unit_price = unit_price or product.list_price
        line_id = sale_line_obj.create({'sale': sale,
                    'product': product.id,
                    'unit_price': unit_price,
                    'quantity': qty,
                })

        line = sale_line_obj.browse(line_id)
        configuration_id = configuration_obj.search([])[0]
        configuration = configuration_obj.browse(configuration_id)
        if configuration.display_port:
            self._display.show_sale_line(line)
        return line_id

    def cash_sale(self, sale_id, cash_amount):
        pool = Pool()
        receipt = pool.get('pos_cash.receipt', 'report')
        configuration_obj = pool.get('pos_cash.configuration')

        configuration_id = configuration_obj.search([])[0]
        configuration = configuration_obj.browse(configuration_id)
        sale = self.browse(sale_id)
        drawback = self.get_drawback([sale_id], '')

        total_paid = sale.total_paid
        if total_paid <= cash_amount:
            self.write(sale.id, {'total_paid': cash_amount})


        if configuration.display_port:
            self._display.show_paid(sale)
        if configuration.logo:
            receipt.kick_cash_drawer()
        if configuration.printer_port:
            receipt.print_sale(sale)

        return drawback


    def get_drawback(self, ids, name):
        res = {}
        for sale in self.browse(ids):
            if sale.total_paid == Decimal(0):
                res[sale.id] = Decimal(0)
            else:
                res[sale.id] = sale.total_paid - sale.total_amount
        return res

    def add_sum(self, ids):
        line_obj = Pool().get('pos_cash.sale.line')
        configuration_obj = Pool().get('pos_cash.configuration')

        configuration_id = configuration_obj.search([])[0]
        configuration = configuration_obj.browse(configuration_id)
        if isinstance(ids, list):
            ids = ids[0]
        if configuration.display_port:
            self._display.show_total(self.browse(ids))
        return line_obj.create({'sale': ids, 'line_type': 'sum'})

    def set_quantity(self, ids, quantity):
        line_obj = Pool().get('pos_cash.sale.line')
        res = line_obj.write(ids, {'quantity': int(quantity)})
        if res:
            self._display.show_sale_line(line_obj.browse(ids))
        return res

PosCashSale()

STATES = {
    'required': Equal(Eval('line_type'), 'position'),
}
class PosCashSaleLine(ModelSQL, ModelView):
    _name = 'pos_cash.sale.line'

    sale = fields.Many2One('pos_cash.sale', 'POS Sale', required=True,
            ondelete='CASCADE')
    line_type = fields.Selection([('position', 'Position'), ('sum', 'Sum'),
            ('cancellation', 'Cancellation')], 'Line Type', required=True)
    product = fields.Many2One('product.product', 'Product', states=STATES)
    name = fields.Function(fields.Char('Name'), 'get_name')
    unit_price = fields.Numeric('Unit price', digits=(16, 2), states=STATES)
    total = fields.Function(fields.Numeric('Total'), 'get_total')
    quantity = fields.Numeric('Quantity', states=STATES)
    without_tax = fields.Function(fields.Numeric('Without Tax'),
            'get_without_tax')
    taxes = fields.Function(fields.One2Many('account.tax', None, 'Taxes'),
            'get_taxes')

    def default_line_type(self):
        return 'position'

    def default_unit_price(self):
        return Decimal(0)

    def default_quantity(self):
        return 0

    def get_taxes(self, ids, name):
        res = {}
        for line in self.browse(ids):
            res[line.id] = []
            if line.line_type == 'sum':
               continue
            res[line.id] += [x.id for x in line.product.customer_taxes_used]
        return res

    def get_without_tax(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.line_type == 'sum':
                res[line.id] = Decimal('0')
                continue
            taxes = Decimal(0)
            for tax in line.product.customer_taxes_used:
                taxes += tax.percentage

            res[line.id] = line.total / ((taxes/100)+1)
        return res

    def get_name(self, ids, name):
        res = {}
        for rec in self.browse(ids):
            if rec.line_type == 'sum':
                res[rec.id] = 'Sum:'
            else:
                res[rec.id] = rec.product.name
        return res

    def get_total(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.line_type == 'sum':
                lines = self.search([('sale', '=', line.sale),
                        ('create_date', '<', line.create_date),
                        ('line_type', '!=', 'sum')])
                s = Decimal('0')
                for l in self.browse(lines):
                    s += l.total
                res[line.id] = s
            else:
                res[line.id] = line.unit_price * line.quantity
        return res

PosCashSaleLine()




