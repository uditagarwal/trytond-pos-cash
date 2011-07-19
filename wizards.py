#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pool import Pool

class AddProductSelect(ModelView):
    _name = 'pos_cash.sale.add_product.select'
    _description = 'Select Product'

    product = fields.Many2One('product.product', 'Product')
    quantity = fields.Numeric('Quantity')

    def default_quantity(self):
        return 1

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
        if (not active_id):
            self.raise_user_error('No active ID found!')
        sale_obj = Pool().get('pos_cash.sale')
        sale = sale_obj.browse(active_id)
        sale_obj.add_product(sale, data['form']['product'],
                data['form']['quantity'])

WizardAddProduct()
