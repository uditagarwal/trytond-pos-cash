#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool

class Template(ModelSQL, ModelView):
    _name = 'product.template'

    def get_account(self, ids, name):
        account_obj = Pool().get('account.account')
        res = {}
        name = name[:-5]
        for product in self.browse(ids):
            if product[name]:
                res[product.id] = product[name].id
            else:
                if product.category[name]:
                    res[product.id] = product.category[name].id
                else:
                    res[product.id] = False
                    # self.raise_user_error('missing_account',
                    #         (product.name, product.id))
        return res

    def get_taxes(self, ids, name):
        res = {}
        name = name[:-5]
        for product in self.browse(ids):
            if product.taxes_category:
                res[product.id] = []
                c = product.category
                while c:
                    res[product.id] += [x.id for x in c[name]]
                    c = c.parent
            else:
                res[product.id] = [x.id for x in product[name]]
        return res

Template()
