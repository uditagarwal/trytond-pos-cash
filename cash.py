#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from decimal import Decimal
import serial
from escpos import escpos

from trytond.model import ModelSQL, ModelView, ModelSingleton, fields
from trytond.pyson import Eval, Equal
from trytond.pool import Pool


__all__ = ['PosCashConfiguration', 'PosCashSale', 'PosCashSaleLine']


class PosCashConfiguration(ModelSingleton, ModelSQL, ModelView):
    'Pos Cash Configuration'
    __name__ = 'pos_cash.configuration'

    sequence = fields.Many2One('ir.sequence.strict', 'Sequence', help='Receipt '
            'number Sequence', required=True)
    printer_port = fields.Char(string='Printer port', help='Port type the '
            'receipt printer is conntected to.')
    display_port = fields.Char('Display port', help='Like /dev/ttyS0')
    display_baud = fields.Numeric('BAUD-Rate', digits=(10,0))
    display_digits = fields.Numeric('Digits per row', digits=(10,0))
    company = fields.Many2One('company.company', 'Company')
    logo = fields.Binary('Receipt Logo')

    @classmethod
    def __setup__(cls):
        super(PosCashConfiguration, cls).__init__()
        cls._rpc.update({
            'test_printer': True,
            'test_display': True,
        })

    @staticmethod
    def default_printer_port():
        """
        Sets the deafult value for printer_port
        """
        return '/dev/lp0'

    @staticmethod
    def default_display_port():
        """
        Sets default for display_port
        """
        return '/dev/ttyS0'

    @staticmethod
    def default_display_baud():
        """
        Sets default for display_port
        """
        return 9600

    @classmethod
    def test_printer(cls, configurations):
        """
        Tests printer
        """
        receipt = Pool().get('pos_cash.receipt', 'report')
        receipt.test_printer()

    @classmethod
    def test_display(cls, configurations):
        """
        Tesing display port
        """
        PosCashConfiguration = Pool().get('pos_cash.configuration')

        configuration = PosCashConfiguration.search([])[0]

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


class PosCashSale(ModelSQL, ModelView):
    __name__ = 'pos_cash.sale'

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

    @classmethod
    def __setup__(cls):
        super(PosCashSale, cls).__setup__()
        cls._disp = False
        cls._rpc.update({
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

    @staticmethod
    def default_receipt_code():
        """
        Sets default for receipt_code
        """
        PosCashConfiguration = Pool().get('pos_cash.configuration')
        SequenceStrict = Pool().get('ir.sequence.strict')

        config = PosCashConfiguration(1)
        seq_code = SequenceStrict.get_id(config.sequence.id)
        res = '%04d%s' % (config.company.id, seq_code)
        return res

    @classmethod
    def get_total_amount(cls, sales, name):
        """
        Returns the total amount of the sale

        :param sales: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for sale in sales:
            total = Decimal(0)
            for line in sale.lines:
                total += line.quantity * line.unit_price
            res[sale.id] = total
        return res

    @classmethod
    def get_taxes(cls, sales, name):
        """
        Returns the tax of the sale

        :param sales: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for sale in sales:
            taxes = []
            for line in sale.lines:
                for tax in line.taxes:
                    if tax.id not in taxes:
                        taxes.append(tax.id)
            res[sale.id] = taxes
        return res

    @classmethod
    def get_total_tax(cls, sales, name):
        """
        Returns the total tax of the sale

        :param sales: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for sale in sales:
            res[sale.id] = sale.total_amount - sale.total_without_tax
        return res

    @classmethod
    def get_without_tax(cls, sales, name):
        """
        Returns the sale without tax

        :param sales: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for sale in sales:
            amount = Decimal(0)
            for line in sale.lines:
                amount += line.without_tax
            res[sale.id] = amount
        return res

    @classmethod
    def add_product(cls, sale, product, qty, unit_price=None):
        """
        Adds Product
        """
        pool = Pool()
        Product = pool.get('product.product')
        PosCashConfiguration = pool.get('pos_cash.configuration')
        PosCashSaleLine = pool.get('pos_cash.sale.line')

        product = Product(product)
        unit_price = unit_price or product.list_price
        line = PosCashSaleLine.create({
            'sale': sale,
            'product': product.id,
            'unit_price': unit_price,
            'quantity': qty,
        })

        configuration = PosCashConfiguration.search([])[0]
        if configuration.display_port:
            cls._display.show_sale_line(line)
        return line

    def cash_sale(self, cash_amount):
        """
        Sale's Cash
        """
        pool = Pool()
        receipt = pool.get('pos_cash.receipt', 'report')
        PosCashConfiguration = pool.get('pos_cash.configuration')

        configuration = PosCashConfiguration.search([])[0]
        drawback = self.get_drawback([self.id], '')

        total_paid = self.total_paid
        if total_paid <= cash_amount:
            self.write([self], {'total_paid': cash_amount})

        if configuration.display_port:
            self._display.show_paid()
        if configuration.logo:
            receipt.kick_cash_drawer()
        if configuration.printer_port:
            receipt.print_sale()

        return drawback

    @classmethod
    def get_drawback(cls, sales, name):
        """
        Returns the drawback of the sales

        :param sales: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for sale in sales:
            if sale.total_paid == Decimal(0):
                res[sale.id] = Decimal(0)
            else:
                res[sale.id] = sale.total_paid - sale.total_amount
        return res

    @classmethod
    def add_sum(cls, sales):
        """
        Returns the sum
        """
        PosCashSaleLine = Pool().get('pos_cash.sale.line')
        PosCashConfiguration = Pool().get('pos_cash.configuration')

        configuration = PosCashConfiguration.search([])[0]
        if configuration.display_port:
            cls._display.show_total(sales)
        return PosCashSaleLine.create({'sale': sales, 'line_type': 'sum'})

    @classmethod
    def set_quantity(cls, sales, quantity):
        """
        Set the quantity
        """
        PosCashSaleLine = Pool().get('pos_cash.sale.line')

        res = PosCashSaleLine.write([sales], {'quantity': int(quantity)})
        if res:
            cls._display.show_sale_line(PosCashSaleLine(sales))
        return res


STATES = {
    'required': Equal(Eval('line_type'), 'position'),
}

class PosCashSaleLine(ModelSQL, ModelView):
    'Pos Cash Sale Line'
    __name__ = 'pos_cash.sale.line'

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

    @staticmethod
    def default_line_type():
        """
        Sets default for line_type
        """
        return 'position'

    @staticmethod
    def default_unit_price():
        """
        Sets default for unit_price
        """
        return Decimal(0)

    @staticmethod
    def default_quantity():
        """
        Sets default for quantity
        """
        return 0

    @classmethod
    def get_taxes(cls, lines, name):
        """
        Returns the taxes

        :param lines: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for line in lines:
            res[line.id] = []
            if line.line_type == 'sum':
               continue
            res[line.id] += [x.id for x in line.product.customer_taxes_used]
        return res

    @classmethod
    def get_without_tax(cls, lines, name):
        """
        Returns the salesline without tax

        :param lines: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for line in lines:
            if line.line_type == 'sum':
                res[line.id] = Decimal('0')
                continue
            taxes = Decimal(0)
            for tax in line.product.customer_taxes_used:
                taxes += tax.percentage

            res[line.id] = line.total / ((taxes/100)+1)
        return res

    @classmethod
    def get_name(cls, lines, name):
        """
        Returns the name

        :param lines: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for rec in lines:
            if rec.line_type == 'sum':
                res[rec.id] = 'Sum:'
            else:
                res[rec.id] = rec.product.name
        return res

    @classmethod
    def get_total(cls, lines, name):
        """
        Returns the total salelines

        :param lines: List of active records
        :param name: Field name
        :return: A dictionary of updated fields & values
        """
        res = {}
        for line in lines:
            if line.line_type == 'sum':
                lines = cls.search([('sale', '=', line.sale),
                        ('create_date', '<', line.create_date),
                        ('line_type', '!=', 'sum')])
                s = Decimal('0')
                for l in lines:
                    s += l.total
                res[line.id] = s
            else:
                res[line.id] = line.unit_price * line.quantity
        return res
