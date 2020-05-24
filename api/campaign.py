from api.character import Character
import json
import time
import shutil, os

def default(dct,k,default=None): # returns a default value if k is not a key of dct
    if k in dct.keys():
        return dct[k]
    else:
        return default

class Campaign:
    @classmethod
    def new(cls, **kwargs): # returns a Campaign instance and creates relevant folders and manifest dict for serialization
        manifest = {
            'meta':{},
            'characters':[],
            'homebrew':[],
            'maps':{}
        }
        manifest['meta']['name'] = default(kwargs,'name',default=time.ctime())
        manifest['meta']['folder'] = default(kwargs,'directory',os.path.join('saves',manifest['meta']['name']))
        os.mkdir(manifest['meta']['folder'])
        os.mkdir(os.path.join(manifest['meta']['folder'],'maps'))
        os.mkdir(os.path.join(manifest['meta']['folder'],'image_assets'))

        return cls(manifest)
    
    @classmethod
    def from_json(cls, path=None, data=None): # returns Campaign instance from mainfest.json
        if path:
            with open(path,'r') as f:
                return cls(json.load(f))
        if data:
            return cls(json.loads(data))
    
    def __init__(self,manifest):
        self.maps = manifest['maps']
        self.homebrew = manifest['homebrew']
        self.characters = manifest['characters']
        self.name = manifest['meta']['name']
        self.folder = manifest['meta']['folder']
    
    def serialize(self,as_dict=False):
        data = {
            'meta':{
                'name':self.name,
                'folder':self.folder
            },
            'characters':self.characters,
            'homebrew':self.homebrew,
            'maps':self.maps
        }
        clist = []
        for c in data['characters']:
            if type(c) == str:
                clist.append(c)
            else:
                clist.append(c.to_json())
        data['characters'] = clist
        if not as_dict:
            return json.dumps(data)
        return data

    def new_character(self, data):
        if data.startswith('https://docs.google.com/spreadsheets'):
            char = Character(gurl=data.split('/')[5])
        elif data.startswith('{'):
            char = Character(_json=data)
        else:
            char = Character(ddbid=data)
        
        self.characters.append(char)
    
    def add_map(self,path):
        map_name = os.path.split(path).split('.')
        map_path = path
        self.maps[name] = {
            'data':{},
            'path':path
        }
    
    def get_map(self,name):
        pass
