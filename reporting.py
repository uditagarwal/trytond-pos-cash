#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from escpos import escpos
from decimal import Decimal
import base64
import cStringIO
import datetime
import serial

from trytond.transaction import Transaction
from trytond.report import Report
from trytond.pool import Pool

_ROW_CHARACTERS = 42
_DIGITS = 9


__all__ = ['Receipt', 'Display']


class Receipt(Report):
    """
    Class to create Reciepts for the Sale Processed
    """
    __name__ = 'pos_cash.receipt'

    @classmethod
    def __setup__(cls):
        super(Receipt, cls).__setup__()
        cls._config = False

    def load_config(self):
        """
        Loads printer port from Configuration
        """
        Configuration = Pool().get('pos_cash.configuration')

        self._port = None
        self._logo = None
        configuration = Configuration.search([])[0]

        self._config = configuration
        if configuration.printer_port:
            self._port = escpos.FileDevice(self._config.printer_port)
        if self._config.logo:
            self._logo = base64.decodestring(self._config.logo)

    def _open_device(self):
        self._printer = None

        if not self._config:
            self.load_config()

        if self._port:
            self._port.open_device()
            self._printer = escpos.Printer(self._port)

    def _close_device(self):
        if self._port:
            self._port.close_device()
        if self._printer:
            del self._printer

    def printing(f):
        def p(self, *p, **kw):
            self._open_device()
            try:
                res = f(self, *p, **kw)
            finally:
                self._close_device()
            return res
        return p

    @printing
    def test_printer(self):
        """
        Function to test if printer is working
        """
        Configuration = Pool().get('pos_cash.configuration')

        configuration = Configuration.search([])[0]
        if configuration.printer_port:
            self.print_logo()
            self._printer.text('\n\n')
            self.print_impressum()
            self._printer.text('\n\n\n')
            self._printer.cut()

    def print_logo(self):
        self._printer.set(align='center')
        self._printer.image(cStringIO.StringIO(self._logo))
        self._printer.text('\n')

    def print_impressum(self):
        company = self._config.company
        address = company.addresses[0]

        impressum = '\n'.join([company.name,
            address.street,
            address.zip + ' ' + address.city])
        self._printer.set(align='center')
        self._printer.text(impressum + '\n')

    @printing
    def kick_cash_drawer(self):
        self._printer.cashdraw(2)

    @printing
    def print_sale(self, sale):
        """
        Function to print the reciept for the sale
        """
        Lang = Pool().get('ir.lang')

        lang = Lang.search([('code', '=', Transaction().language)])

        def print_split(left, right):
            len_left = _ROW_CHARACTERS - len(right) - 1
            left = left[:len_left]
            left += (len_left-len(left)+1) * ' '
            printer.text(left)
            printer.text(right + '\n')

        printer = self._printer

        self.print_logo()
        self.print_impressum()
        printer.set(align='left')
        taxes = {}
        i = 0
        for tax in sale.taxes:
            i += 1
            taxes[tax.id] = {}
            taxes[tax.id]['code'] = str(i)
            taxes[tax.id]['rec'] = tax
            taxes[tax.id]['amount'] = Decimal(0)

        printer.text('\n')
        for line in sale.lines:
            if line.line_type == 'sum':
                print_split('Total:', self.format_lang(line.total, lang) + '  ')
                printer.text('\n')
            else:
                tax_codes = []
                for tax in line.taxes:
                    tax_codes.append(taxes[tax.id]['code'])
                    taxes[tax.id]['amount'] += line.unit_price * line.quantity
                tax_codes = ' '.join(tax_codes)

                printer.text(line.name[:_ROW_CHARACTERS] + '\n')
                pos_text = '  %s x %s' % (
                            self.format_lang(line.quantity, lang, digits=1),
                            self.format_lang(line.unit_price, lang)
                        )
                total = self.format_lang(line.total, lang)
                print_split(pos_text, total + ' ' + tax_codes)


        print_split('Cash:',
                self.format_lang(sale.total_paid, lang) + '  ')
        print_split('Drawback:',
                self.format_lang(sale.drawback, lang) + '  ')
        printer.text('\n'*2)
        cols = 4
        col_width = int(_ROW_CHARACTERS / 4)
        f = lambda x, l: printer.text(x[:l] + (l-len(x)) * ' ')
        f('Kind', col_width)
        f('Without', col_width)
        f('Tax', col_width)
        f('With', col_width)
        printer.text('\n')
        for tax in taxes:
            t = taxes[tax]['rec']
            f(taxes[tax]['code'] + '=' + self.format_lang(t.percentage, lang) + '%',
                    col_width)
            with_tax = taxes[tax]['amount']
            without_tax = with_tax / ((t.percentage/100) +1)
            tax = with_tax-without_tax
            f(self.format_lang(without_tax, lang), col_width)
            f(self.format_lang(tax, lang), col_width)
            f(self.format_lang(with_tax, lang), col_width)
            printer.text('\n')

        printer.text('\n'*2)
        printer.set(align='center')
        printer.barcode(sale.receipt_code, 'CODE128B', 3, 50,'','')
        printer.text('\n'*2)
        printer.text(self.format_lang(datetime.datetime.now(), lang, date=True))
        printer.cut()

class Display(Report):
    """
    Function to display report of the sale
    """
    __name__ = 'pos_cash.display'

    def __setup__(cls):
        super(Display, cls).__setup__()
        cls._display = False

    def _get_lang(self):
        """
        Gets the language set in the Tryton System
        """
        Lang = Pool().get('ir.lang')

        return Lang.search([('code', '=', Transaction().language)])[0]

    def load_display(self):
        """
        Loads display
        """
        Configuration = Pool().get('pos_cash.configuration')

        configuration = Configuration.search([])[0]

        lang = self._get_lang()
        if configuration.display_port:
            self._display = escpos.Display(serial.Serial(
                configuration.display_port, configuration.display_baud),
                digits=int(configuration.display_digits))
            self._display.set_cursor(False)

    def displaying(f):
        def p(self, *p, **kw):
            if not self._display:
                self.load_display()
            return f(self, *p, **kw)
        return p

    @displaying
    def show_sale_line(self, sale_line):
        """
        Shows the lines of the sale
        """
        Configuration = Pool().get('pos_cash.configuration')

        configuration = Configuration.search([])[0]

        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.set_align('left')
            self._display.text(sale_line.product.name)
            self._display.new_line()
            self._display.text('%s x %s' % (
                            self.format_lang(sale_line.quantity, lang, digits=0),
                            self.format_lang(sale_line.unit_price, lang),
                        )
                    )
            self._display.set_align('right')
            self._display.text(self.format_lang(sale_line.total, lang))

    @displaying
    def show_total(self, sale):
        """
        Shows total of sale line
        """
        Configuration = Pool().get('pos_cash.configuration')

        configuration = Configuration.search([])[0]

        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.text('Total:')
            self._display.set_align('right')
            self._display.text(self.format_lang(sale.total_amount, lang))

    @displaying
    def show_paid(self, sale):
        """
        Show amount paid by the customer
        """
        Configuration = Pool().get('pos_cash.configuration')

        configuration = Configuration.search([])[0]

        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.text('Paid:')
            self._display.set_align('right')
            f = lambda x: self.format_lang(x, lang)
            self._display.text(f(sale.total_paid))
            self._display.new_line()
            self._display.set_align('left')
            self._display.text('Drawback:')
            self._display.set_align('right')
            self._display.text(f(sale.drawback))
