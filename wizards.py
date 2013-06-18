#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pool import Pool


__all__ = [
    'AddProductSelect', 'WizardAddProduct', 'CashAmountEnter', \
    'WizardCashSale'
]

class AddProductSelect(ModelView):
    'Add Product Select'
    __name__ = 'pos_cash.sale.add_product.select'

    product = fields.Many2One('product.product', 'Product',
            on_change=['product'])
    unit_price = fields.Numeric('Unit price', digits=(16, 2))
    quantity = fields.Numeric('Quantity')

    @staticmethod
    def default_quantity():
        """
        Sets default for quantity
        """
        return 1

    def on_change_product(self):
        """
        Changes the value of product

        :return: updated value of unit_price
        """
        if not self.product:
            return {}
        return {'unit_price': self.product.list_price}


class WizardAddProduct(Wizard):
    'Wizard Add Product'
    __name__ = 'pos_cash.sale.add_product'

    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'pos_cash.sale.add_product.select',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Add', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_add',
                'state': 'end',
            },
        },
    }

    def _action_add(self, data):
        """
        Action to add product
        """
        PosCashSale = Pool().get('pos_cash.sale')

        active_id = Transaction().context.get('active_id', False)
        form = data['form']
        PosCashSale.add_product(active_id, form['product'], form['quantity'],
                form['unit_price'])


class CashAmountEnter(ModelView):
    'Cash Amount Enter'
    __name__ = 'pos_cash.sale.cash_amount_enter'

    cash_amount = fields.Numeric('Cash amount', required=True)


class WizardCashSale(Wizard):
    'Wizard Cash Sale'
    __name__ = 'pos_cash.sale.cash'

    states = {

        'init': {
            'result': {
                'type': 'form',
                'object': 'pos_cash.sale.cash_amount_enter',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Cash', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_cash_received',
                'state': 'end',
            },
        },
    }


    def _action_cash_received(self, data):
        """
        Action to receive cash
        """
        PosCashSale = Pool().get('pos_cash.sale')
        
        active_id = Transaction().context.get('active_id', False)
        PosCashSale.cash_sale(active_id, data['form']['cash_amount'])
