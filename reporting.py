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

class Receipt(Report):
    _name = 'pos_cash.receipt'

    def __init__(self):
        super(Receipt, self).__init__()
        self._config = False

    def load_config(self):
        config = Pool().get('pos_cash.configuration')
        config = config.browse(1)
        self._config = config
        self._port = escpos.FileDevice(config.printer_port)
        self._logo = base64.decodestring(self._config.logo)

    def _open_device(self):
        if not self._config:
            self.load_config()

        self._port.open_device()
        self._printer = escpos.Printer(self._port)

    def _close_device(self):
        self._port.close_device()
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
        lang_obj = Pool().get('ir.lang')
        lang, = lang_obj.search([('code', '=', Transaction().language)])
        lang = lang_obj.browse(lang)

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

Receipt()


class Display(Report):
    _name = 'pos_cash.display'

    def __init__(self):
        super(Display, self).__init__()
        self._display = False

    def _get_lang(self):
        lang_obj = Pool().get('ir.lang')
        lang, = lang_obj.search([('code', '=', Transaction().language)])
        return lang_obj.browse(lang)

    def load_display(self):
        config_obj = Pool().get('pos_cash.configuration')
        config = config_obj.browse(1)
        lang = self._get_lang()
        self._display = escpos.Display(serial.Serial(
                config.display_port, config.display_baud),
                digits=int(config.display_digits))
        self._display.set_cursor(False)

    def displaying(f):
        def p(self, *p, **kw):
            if not self._display:
                self.load_display()
            return f(self, *p, **kw)
        return p

    @displaying
    def show_sale_line(self, sale_line):
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
        lang = self._get_lang()
        self._display.clear()
        self._display.text('Total:')
        self._display.set_align('right')
        self._display.text(self.format_lang(sale.total_amount, lang))

    @displaying
    def show_paid(self, sale):
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


Display()

