#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from escpos import escpos
import base64
import cStringIO

class Printer(escpos.Escpos):

    def __init__(self, port):
        self._parallel_port = port

    def open_device(self):
        self._port = open(self._parallel_port, 'wb')

    def close_device(self):
        self._port.close()

    def _raw(self, msg):
        self._port.write(msg)

class Receipt(object):

    def __init__(self, config):
        self._config = config
        self._printer = Printer(config.printer_port)
        self._logo = cStringIO.StringIO(base64.decodestring(self._config.logo))

    def test_printer(self):
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

    def print_impressum(self):
        company = self._config.company
        address = company.addresses[0]

        impressum = '\n'.join([company.name,
            address.street,
            address.zip + ' ' + address.city])
        self._printer.set(align='center')
        self._printer.text(impressum)


