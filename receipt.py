#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from escpos import escpos
from decimal import Decimal
import base64
import cStringIO
import datetime

from trytond.transaction import Transaction
from trytond.report import Report
from trytond.pool import Pool

_ROW_CHARACTERS = 42
_DIGITS = 9

class Printer(escpos.Escpos):

    def __init__(self, port):
        self._parallel_port = port

    def open_device(self):
        self._port = open(self._parallel_port, 'wb')

    def close_device(self):
        self._port.close()

    def _raw(self, msg):
        self._port.write(msg)

class Receipt(Report):
    _name = 'pos_cash.receipt'

    def __init__(self):
        super(Receipt, self).__init__()
        self._config = False

    def load_config(self):
        config = Pool().get('pos_cash.configuration')
        config = config.browse(1)
        self._config = config
        self._printer = Printer(config.printer_port)
        self._logo = cStringIO.StringIO(base64.decodestring(self._config.logo))

    def test_printer(self):
        if not self._config:
            self.load_config()

        self._printer.open_device()
        self.print_logo()
        self._printer.text('\n\n')
        self.print_impressum()
        self._printer.text('\n\n\n')
        self._printer.cut()
        self._printer.close_device()

    def print_logo(self):
        self._printer.set(align='center')
        self._printer.image(self._logo)
        self._printer.text('\n')

    def print_impressum(self):
        company = self._config.company
        address = company.addresses[0]

        impressum = '\n'.join([company.name,
            address.street,
            address.zip + ' ' + address.city])
        self._printer.set(align='center')
        self._printer.text(impressum + '\n')

    def print_sale(self, sale):
        self.load_config()
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
        printer.open_device()
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
            tax_codes = []
            for tax in line.product.customer_taxes_used:
                tax_codes.append(taxes[tax.id]['code'])
                taxes[tax.id]['amount'] += line.unit_price * line.quantity
            tax_codes = ' '.join(tax_codes)
            printer.text(line.product.rec_name[:_ROW_CHARACTERS] + '\n')
            pos_text = '  %s x %s' % (
                        self.format_lang(line.quantity, lang, digits=1),
                        self.format_lang(line.unit_price, lang)
                    )
            total = self.format_lang(line.total, lang)
            print_split(pos_text, total + ' ' + tax_codes)


        print_split('', '-' * _DIGITS + '  ')
        print_split('Total:',
                self.format_lang(sale.total_amount, lang) + '  ')
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
        printer.close_device()

Receipt()

