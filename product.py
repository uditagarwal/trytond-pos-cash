#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView
from trytond.pool import Pool


__all__ = ['Template']


class Template(ModelSQL, ModelView):
    """
        Template for the product to appear in lines in the POS System
    """
    __name__ = 'product.template'

    @classmethod
    def get_account(cls, products, name):
        """
        Gets the account of the current purchaser
        """
        Account = Pool().get('account.account')

        res = {}
        name = name[:-5]
        for product in products:
            if product[name]:
                res[product.id] = product[name].id
            else:
                res[product.id] = product.category[name] and \
                        product.category[name].id or None
        return res

    @classmethod
    def get_taxes(cls, products, name):
        """
        Gets the taxes for the products
        """
        res = {}
        name = name[:-5]
        for product in products:
            if product.taxes_category:
                res[product.id] = []
                c = product.category
                while c:
                    res[product.id] += [x.id for x in c[name]]
                    c = c.parent
            else:
                res[product.id] = [x.id for x in product[name]]
        return res
