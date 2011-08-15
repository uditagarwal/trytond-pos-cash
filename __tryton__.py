#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'POS Cash',
    'version' : '0.1.0',
    'author' : 'Max Holtzberg',
    'email': 'max@holtzberg.de',
    'website': 'http://www.tryton.org/',
    'description': 'Provides functionality for cashing customers on POS',
    'depends' : [
        'ir',
        'res',
        'product',
        'account',
        'account_product',
    ],
    'xml' : [
        'cash.xml',
    ],
    'translation': [
    ]
}

