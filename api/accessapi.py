import json
import os
import requests
from urllib.parse import urljoin

class Item:
    def resolve_list(self,lst):
        rl = []
        for i in lst:
            if type(i) == dict:
                rl.append(Item(i))
            elif type(i) == list:
                rl.append(self.resolve_list(i))
            else:
                rl.append(i)
        return rl
    def __init__(self,dct):
        self.json = dct
        for d in dct.keys():
            if type(dct[d]) == dict:
                setattr(self,d,Item(dct[d]))
            elif type(dct[d]) == list:
                setattr(self,d,self.resolve_list(dct[d]))
            else:
                setattr(self,d,dct[d])

def get(resource_type,**terms):
    terms['limit'] = 10000
    response = requests.get('https://api.open5e.com/'+resource_type+'/',params=terms)
    jsondata = response.json()
    dat = []
    for i in jsondata['results']:
        dat.append(Item(i))
    return dat


    


