#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pool import Pool

class AddProductSelect(ModelView):
    _name = 'pos_cash.sale.add_product.select'
    _description = 'Select Product'

    product = fields.Many2One('product.product', 'Product',
            on_change=['product'])
    unit_price = fields.Numeric('Unit price', digits=(16, 2))
    quantity = fields.Numeric('Quantity')

    def default_quantity(self):
        return 1

    def on_change_product(self, vals):
        if not vals.get('product'):
            return {}
        product_obj = Pool().get('product.product')
        product = product_obj.browse(vals['product'])
        return {'unit_price': product.list_price}



AddProductSelect()


class WizardAddProduct(Wizard):
    _name = 'pos_cash.sale.add_product'

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
        active_id = Transaction().context.get('active_id', False)
        sale_obj = Pool().get('pos_cash.sale')
        form = data['form']
        sale_obj.add_product(active_id, form['product'], form['quantity'],
                form['unit_price'])

WizardAddProduct()


class CashAmountEnter(ModelView):
    _name = 'pos_cash.sale.cash_amount_enter'
    _description = 'Select Product'

    cash_amount = fields.Numeric('Cash amount', required=True)

CashAmountEnter()


class WizardCashSale(Wizard):
    _name = 'pos_cash.sale.cash'

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
        active_id = Transaction().context.get('active_id', False)
        sale_obj = Pool().get('pos_cash.sale')
        sale_obj.cash_sale(active_id, data['form']['cash_amount'])

WizardCashSale()

