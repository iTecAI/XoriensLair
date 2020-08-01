import os, time, shutil
if not os.path.exists(os.path.join('logs','dump')):
    os.makedirs(os.path.join('logs','dump'))

os.environ['NUMEXPR_MAX_THREADS'] = '16'

from api import *
import base64
import json
import datetime
from threading import Thread
from hashlib import sha256
from random import random,randint
import pickle
import logging
import logging.config
from urllib.parse import urlparse
import dice

# options
IP = 'localhost'
S_PORT = 1022
A_PORT = 1023
DIR = os.path.join(os.getcwd(),'client/')

LOGMODE = 'debug'
#LOGMODE = 'server'

MAX_LOG_SIZE = 10000000 # Max log size 10 MB

class Session:
    def __init__(self,instance,_id,session=None,name='None'):
        self.logger = logging.LoggerAdapter(logging.getLogger('session_'+LOGMODE),{'sessionname':name})
        self.id = _id
        if session:
            self.logger.debug('Loaded session from file.')
            session = json.loads(session)
            self.maps = session['maps']
            self.characters = session['characters']
            self.character_urls = session['character_urls']
            self.character_icons = session['character_icons']
            self.homebrew = session['homebrew']
            for k in self.characters.keys():
                if type(self.characters[k]) == str:
                    self.characters[k] = Character(_json=self.characters[k])
                else:
                    self.characters[k] = Character(_json=self.characters[k])
        else:
            self.logger.debug('Created new session.')
            self.maps = []
            self.characters = {}
            self.character_urls = {}
            self.character_icons = {}
            self.homebrew = []
        
        self.initiative_data = {
            'active':False,
            'order':{},
            'rolls':[],
            'index':0,
            'next':None
        }
        self.instance = instance

    def jsonify(self):
        ndct = {}
        for k in self.characters.keys():
            if type(self.characters[k]) == dict:
                ndct[k] = self.characters[k]
            elif type(self.characters[k]) == str:
                ndct[k] = json.loads(self.characters[k])
            else:
                ndct[k] = json.loads(self.characters[k].to_json())
        return {
            'maps':self.maps,
            'characters':ndct,
            'character_urls':self.character_urls,
            'character_icons':self.character_icons,
            'initiative':self.initiative_data,
            'homebrew':self.homebrew
        }
    
    def save(self,fp,args): # No arguments
        self.logger.debug('Saved session.')
        return {'save':self.jsonify()}

    def load_sheet(self,fp,args): # [URL]
        self.logger.debug('Loading sheet with URL '+args[0]+' for '+fp)
        url = args[0]
        if url.startswith('https://docs.google.com/spreadsheets'):
            char = Character(gurl=url.split('/')[5])
        elif url.startswith('{'):
            char = Character(_json=url)
        else:
            pass
        self.characters[fp] = char
        self.character_urls[fp] = url
        self.character_icons[fp] = 'Dice'
        return {'code':200}
    
    def load_homebrew(self,fp,args): # [CritterDB Creature or Bestiary URL]
        self.logger.debug('Loading homebrew from '+str(args[0]))
        url = args[0]
        if 'critterdb.com' in url:
            try:
                ID = urlparse(url).fragment.split('/')[3]
                if 'bestiary' in url:
                    self.homebrew.extend([i for i in api_get_bestiary(ID)])
                elif 'creature' in url:
                    self.homebrew.append(api_get_creature(ID))
                else:
                    self.logger.warning('Failed to load homebrew from '+str(url)+', invalid URL')
                    return {'code':400,'reason':'URL invalid.'}
                self.logger.debug('Homebrew loading success.')
                return {'code':200}
            except APIError:
                self.logger.exception('Exception in fetching '+str(url)+':')
                return {'code':404,'reason':'API Error'}
        else:
            self.logger.warning('Failed to load homebrew from '+str(url)+', invalid URL')
            return {'code':400,'reason':'URL invalid.'}
    
    def update_sheet(self,fp,args): # []
        if fp in self.character_urls.keys():
            return self.load_sheet(fp,[self.character_urls[fp]])
            self.logger.debug('Updated sheet for '+fp)
        else:
            self.logger.warning('Failure to update sheet for '+fp)
            return {'code':404,'reason':'PC not found. Load a sheet.'}
            
    
    def load_map(self,fp,args): # [Data URL, # Rows, # Columns, Feet/grid square]
        _id = sha256(str(time.time()*random()).encode('utf-8')).hexdigest()
        self.logger.debug('Loading map with ID '+str(_id))
        url = args[0]
        self.maps.append({
            'image': url,
            'id': _id,
            'grid_data':{
                'rows':args[1],
                'columns':args[2],
                'size':args[3]
            },
            'active': False,
            'markers': [],
            'npcs': {},
            'characters': {},
            'obscuration': {}
        })
        return {'code':200}
    
    def delete_map(self,fp,args): # [Map ID]
        _id = args[0]
        self.logger.debug('Deleting map '+str(_id))
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == _id:
                del self.maps[i]
                return {'code':200}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def modify_map(self,fp,args): # [Map ID, # Rows, # Columns, Feet/square, X, Y, Active]
        self.logger.debug('Modifying map'+str(args[0])+'with args'+str(args))
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['grid_data'] = {
                    'rows':args[1],
                    'columns':args[2],
                    'size':args[3]
                }
                self.maps[i]['active'] = args[4]
                return {'code':200}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def obscure(self,fp,args): # [Map ID, Top Corner X, Top Corner Y, Width, Height, Obscuration ID]
        self.logger.debug('Obscuring map '+args[0]+' with args '+str(args))
        args[1] = float(args[1])
        args[2] = float(args[2])
        args[3] = float(args[3])
        args[4] = float(args[4])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['obscuration'][args[5]] = [args[1],args[2],args[3],args[4]]
                return {'code':200}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def remove_obscure(self,fp,args): # [Map ID, Obscuration ID]
        self.logger.debug('Removing obscure '+str(args[1])+' from map '+str(args[0]))
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if args[1] in self.maps[i]['obscuration'].keys():
                    del self.maps[i]['obscuration'][args[1]]
                    return {'code':200}
                else:
                    self.logger.warning('User error - Obscure not found. User '+fp)
                    return {'code':404,'reason':'Obscure not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def activate_pc(self,fp,args): # [Map ID, Icon Name or Data URL, X, Y]
        self.logger.debug('Activating PC for user '+fp)
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['characters'][fp] = {
                    'name':self.characters[fp]['name'],
                    'pos':[int(args[2]),int(args[3])],
                    'icon':args[1]
                }
                self.logger.debug('Activated '+self.characters[fp]['name']+' on map '+args[0]+' for user '+fp)
                return {'code':200}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def move_pc(self,fp,args): # [Map ID, X, Y]
        self.logger.debug('Moving '+self.characters[fp]['name']+' on map '+args[0]+' for user '+fp+' to '+str(args[1:]))
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if fp in self.maps[i]['characters'].keys():
                    self.maps[i]['characters'][fp]['pos'] = [int(float(args[1])),int(float(args[2]))]
                    return {'code':200}
                else:
                    self.logger.warning('User error - Character not found. User '+fp)
                    return {'code':404,'reason':'Character not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def modify_pc(self,fp,args): # [ID, Icon, List of keys and values ([['key1|key2|key3','value'],['key4|key5','value']])]
        self.logger.debug('Modifying PC '+args[0]+' with '+args[2])
        if (not args[0] in self.characters.keys()):
            self.logger.warning('User error - Character not found. User '+fp)
            return {'code':404,'reason':'Character not found.'}
        if str(args[1]) != '-1':
            self.character_icons[args[0]] = args[1]
            for m in range(len(self.maps)):
                if args[0] in self.maps[m]['characters'].keys():
                    self.maps[m]['characters'][args[0]]['icon'] = args[1]
        '''if str(args[2]) != '-1':
            self.characters[args[0]]['hp'] = int(args[2])
        if str(args[3]) != '-1':
            self.characters[args[0]]['max_hp'] = int(args[3])
        if str(args[4]) != '-1':
            self.characters[args[0]]['name'] = args[4]
            for m in range(len(self.maps)):
                if args[0] in self.maps[m]['characters'].keys():
                    self.maps[m]['characters'][args[0]]['name'] = args[4]'''
        outcomes = {}
        for i in eval(args[2]):
            try:
                try:
                    val = str(int(i[1]))
                except ValueError:
                    val = '"'+str(i[1])+'"'
                exec('self.characters[args[0]]["'+'"]["'.join(i[0].split('.'))+'"] = '+val)
                outcomes[i[0]] = 1
            except KeyError:
                outcomes[i[0]] = 0
            except IndexError:
                outcomes[i[0]] = 0
        return {'code':200,'data':json.loads(self.characters[args[0]].to_json()),'outcomes':outcomes}
    
    def deactivate_pc(self,fp,args): # [Map ID]
        self.logger.debug('Deactivating PC of User '+fp+' on map '+args[0])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if fp in self.maps[i]['characters'].keys():
                    del self.maps[i]['characters'][fp]
                    return {'code':200}
                else:
                    self.logger.warning('User error - Character not found. User '+fp)
                    return {'code':404,'reason':'Character not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def deactivate_pc_dm(self,fp,args): # [Map ID, PC ID]
        self.logger.debug('DM is deactivating PC of User '+args[1]+' on map '+args[0])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if args[1] in self.maps[i]['characters'].keys():
                    del self.maps[i]['characters'][args[1]]
                    return {'code':200}
                else:
                    self.logger.warning('User error - Character not found. User '+fp)
                    return {'code':404,'reason':'Character not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def assign_pc(self,fp,args): # [Old ID]
        found = False
        self.logger.debug('Assigning PC with ID '+args[0]+' to '+fp)
        for u in range(len(self.instance.sessions[self.id]['users'])):
            if self.instance.sessions[self.id]['users'][u]['fingerprint'] == args[0]:
                del self.instance.sessions[self.id]['users'][u]
                found = True
                break
        if args[0] in self.characters.keys():
            self.characters[fp] = self.characters[args[0]]
            self.character_urls[fp] = self.character_urls[args[0]]
            self.character_icons[fp] = self.character_icons[args[0]]
            del self.characters[args[0]]
            del self.character_urls[args[0]]
            del self.character_icons[args[0]]
            for m in range(len(self.maps)):
                if args[0] in self.maps[m]['characters'].keys():
                    self.maps[m]['characters'][fp] = self.maps[m]['characters'][args[0]]
                    del self.maps[m]['characters'][args[0]]
        if found:
            return {'code':200}
        self.logger.warning('User error - Character not found. User '+fp)
        return {'code':404,'reason':'Character not found'}
            

    def open5e(self,fp,args): 

        '''
        [Resource type (
        spells, 
        monsters, 
        documents, 
        backgrounds, 
        planes, 
        sections, 
        feats, 
        conditions, 
        races, 
        classes, 
        magicitems, 
        weapons, 
        search
        ), 
        **kwargs in "key,value" arrangement]
        '''

        restype = args.pop(0)
        arguments = []
        arg_keys = []
        for a in args:
            sp = a.split(',')
            arguments.append(tuple(sp))
            arg_keys.append(sp[0])
        rs = 'get(restype,'+','.join([n[0]+'="'+n[1]+'"' for n in arguments])+')'
        results = eval(rs)
        data = [i.json for i in results]
        if restype == 'monsters' and 'search' in arg_keys:
            adict = dict(arguments)
            for h in self.homebrew:
                if h['name'] in adict['search'] or adict['search'] in h['name']:
                    data.append(h)

        return {'code':200,'result':json.dumps({'data':data})}
    
    def add_npc(self,fp,args): # [Map ID, Icon, Data, X, Y]
        self.logger.debug('Creating NPC on '+args[0])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['npcs'][sha256(str(time.time()*random()).encode('utf-8')).hexdigest()] = {
                    'icon':args[1],
                    'data':json.loads(args[2]),
                    'pos':[int(args[3]),int(args[4])],
                    'hp':int(json.loads(args[2])['hit_points'])
                }
                return {'code':200}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
  
    def modify_npc(self,fp,args): # [Map ID, NPC ID, Data, Current HP, X, Y]
        self.logger.debug('Modifying NPC '+args[1]+' on map '+args[0])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if args[1] in self.maps[i]['npcs'].keys():
                    self.maps[i]['npcs'][args[1]]['data'] = args[2]
                    self.maps[i]['npcs'][args[1]]['hp'] = args[3]
                    self.maps[i]['npcs'][args[1]]['pos'] = [int(args[4]),int(args[5])]
                    return {'code':200}
                else:
                    self.logger.warning('User error - NPC not found. User '+fp)
                    return {'code':404,'reason':'NPC not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}

    def remove_npc(self,fp,args): # [Map ID, NPC ID]
        self.logger.debug('Removing NPC '+args[1]+' from map '+args[0])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if args[1] in self.maps[i]['npcs'].keys():
                    del self.maps[i]['npcs'][args[1]]
                    return {'code':200}
                else:
                    self.logger.warning('User error - NPC not found. User '+fp)
                    return {'code':404,'reason':'NPC not found.'}
        self.logger.warning('User error - Map not found. User '+fp)
        return {'code':404,'reason':'Map not found.'}
    
    def initiative(self,fp,args): # [Command, Map ID, NPC ID if applicable (otherwise -1)]
        if not args[0] == 'check':
            self.logger.debug('User '+fp+' is executing an initiative subcommand ('+args[0]+') on map '+args[1])
        code, dat = self.instance.check_user({'fingerprint':fp})

        if args[0] == 'roll':
            if dat['type'] == 'pc':
                roll = randint(1,20)+int(self.characters[fp]['skills']['initiative']['value'])+(random()/10)
                data = self.characters[fp].to_json()
                ID = fp
                index = -1
                for i in range(len(self.maps)):
                    if self.maps[i]['id'] == args[1]:
                        index = i
                if index >= 0:
                    name = self.characters[fp]['name']
                    icon = self.maps[index]['characters'][fp]['icon']
                else:
                    return {'code':404,'reason':'Map not found'}
                
            else:
                index = -1
                for i in range(len(self.maps)):
                    if self.maps[i]['id'] == args[1]:
                        index = i
                if index >= 0:
                    if type(self.maps[index]['npcs'][args[2]]['data']) == str:
                        npc = json.loads(self.maps[index]['npcs'][args[2]]['data'])
                    else:
                        npc = self.maps[index]['npcs'][args[2]]['data']
                    name = npc['name']
                    icon = self.maps[index]['npcs'][args[2]]['icon']
                    data = json.dumps(self.maps[index]['npcs'][args[2]]['data'])
                    roll = randint(1,20)+getmod(int(npc['dexterity']))+(random()/10)
                    ID = args[2]
                else:
                    return {'code':404,'reason':'Map not found'}
            
            self.initiative_data['rolls'].append(roll)
            self.initiative_data['rolls'].sort(reverse=True)
            self.initiative_data['order'][roll] = {
                'type':dat['type'],
                'data':data,
                'id':ID,
                'icon':icon,
                'name':name
            }
            self.initiative_data['active'] = True
            return {'code':200,'roll':int(roll),'place':self.initiative_data['rolls'].index(roll)}
        elif args[0] == 'check':
            if len(self.initiative_data['rolls']) == 0 or self.initiative_data['active'] == False:
                self.initiative_data['active'] = False
                return {
                    'code':200,
                    'current':{},
                    'next':{}
                }

            try:
                return {
                    'code':200,
                    'current':self.initiative_data['order'][self.initiative_data['rolls'][self.initiative_data['index']]],
                    'next':self.initiative_data['order'][self.initiative_data['rolls'][self.initiative_data['index']+1]]
                    }
            except IndexError:
                try:
                    return {
                        'code':200,
                        'current':self.initiative_data['order'][self.initiative_data['rolls'][self.initiative_data['index']]],
                        'next':self.initiative_data['order'][self.initiative_data['rolls'][0]]
                        }
                except IndexError:
                    return {
                        'code':200,
                        'current':self.initiative_data['order'][self.initiative_data['rolls'][0]],
                        'next':self.initiative_data['order'][self.initiative_data['rolls'][0]]
                        }
        elif args[0] == 'remove':
            if dat['type'] == 'pc':
                to_delete = None
                for k in self.initiative_data['order'].keys():
                    if self.initiative_data['order'][k]['id'] == fp:
                        to_delete = k
                if to_delete != None:
                    del self.initiative_data['order'][to_delete]
                    self.initiative_data['rolls'].remove(to_delete)
            else:
                to_delete = None
                for k in self.initiative_data['order'].keys():
                    if self.initiative_data['order'][k]['id'] == args[2]:
                        to_delete = k
                if to_delete != None:
                    del self.initiative_data['order'][to_delete]
                    self.initiative_data['rolls'].remove(to_delete)
            return {'code':200,'data':self.initiative_data['rolls']}
        elif args[0] == 'next' and dat['type'] == 'dm':
            self.initiative_data['index'] += 1
            if self.initiative_data['index'] >= len(self.initiative_data['rolls']):
                self.initiative_data['index'] = 0
            return {'code':200,'current':self.initiative_data['order'][self.initiative_data['rolls'][self.initiative_data['index']]]}
        elif args[0] == 'end' and dat['type'] == 'dm':
            self.initiative_data = {
                'active':False,
                'order':{},
                'rolls':[],
                'index':0
            }
            return {'code':200}
        return {'code':404,'reason':'Command not found or forbidden'}
    
    def delete_user(self,fp,args): # [User ID]
        self.logger.debug('Removing PC with ID '+args[0])
        if args[0] in self.characters.keys():
            del self.characters[args[0]]
            del self.character_urls[args[0]]
            del self.character_icons[args[0]]
            for m in range(len(self.maps)):
                if args[0] in self.maps[m]['characters'].keys():
                    del self.maps[m]['characters'][args[0]]
        for u in range(len(self.instance.sessions[self.id]['users'])):
            if self.instance.sessions[self.id]['users'][u]['fingerprint'] == args[0]:
                del self.instance.sessions[self.id]['users'][u]
                return {'code':200}
        
        self.logger.warning('User error - Character not found. User '+fp)
        return {'code':404,'reason':'Character not found'}
    
    def pc_attack(self,fp,args): # [Target, Map ID, Attack data]
        self.logger.debug('PC '+fp+' is attacking '+str(args[0]))
        self.logger.debug('ATK data: '+str(args[2]))
        data = json.loads(args[2])
        damage = int(dice.roll(data['roll']))
        if args[0] in self.characters.keys():
            if int(dice.roll(data['toHit'])) >= int(self.characters[args[0]]['ac']):
                for r in [('vuln',2),('resist',0.5),('immune',0)]:
                    if data['type'] in self.characters[args[0]]['resistances'][r[0]]:
                        damage = damage * r[1]
                damage = int(damage)
                self.characters[args[0]]['hp'] -= damage
                self.logger.debug('PC '+fp+' dealt '+str(damage)+' to '+str(self.characters[args[0]]['name']))
                if self.characters[args[0]]['hp'] < 0:
                    self.characters[args[0]]['hp'] = 0
                    self.logger.debug('PC '+fp+' knocked out PC '+str(args[0]))
                return {'code':200,'result':json.dumps({'hit':True,'damage':damage})}
            else:
                self.logger.debug('PC '+fp+' missed their attack on '+str(args[0]))
                return {'code':200,'result':json.dumps({'hit':False,'damage':None})}
            
        else:
            for m in range(len(self.maps)):
                if args[0] in self.maps[m]['npcs'].keys():
                    if int(dice.roll(data['toHit'])) >= int(self.maps[m]['npcs'][args[0]]['data']['armor_class']):
                        resist = dict(
                            resist = self.maps[m]['npcs'][args[0]]['data']['damage_resistances'].replace(', ','|').split(','),
                            immune = self.maps[m]['npcs'][args[0]]['data']['damage_immunities'].replace(', ','|').split(','),
                            vuln = self.maps[m]['npcs'][args[0]]['data']['damage_vulnerabilities'].replace(', ','|').split(',')
                        )
                        for r in [('vuln',2),('resist',0.5),('immune',0)]:
                            for k in resist[r[0]]:
                                if data['type'] == k:
                                    damage = damage * r[1]
                                    break
                                if 'nonmagic' in k or 'non-magic' in k:
                                    for d in ['piercing','slashing','bludgeoning']:
                                        if data['type'] == d and d in k:
                                            damage = damage * r[1]
                                            break
                        damage = int(damage)
                        self.maps[m]['npcs'][args[0]]['hp'] -= damage
                        self.logger.debug('PC '+fp+' dealt '+str(damage)+' to NPC '+str(args[0]))
                        if self.maps[m]['npcs'][args[0]]['hp'] <= 0:
                            self.logger.debug('PC '+fp+' killed NPC '+str(args[0]))
                            del self.maps[m]['npcs'][args[0]]
                        return {'code':200,'result':json.dumps({'hit':True,'damage':damage})}
                    else:
                        self.logger.debug('PC '+fp+' missed their attack on '+str(args[0]))
                        return {'code':200,'result':json.dumps({'hit':False,'damage':None})}
            self.logger.warning('NPC '+str(args[0])+' not found.')
            return {'code':404,'reason':'NPC '+str(args[0])+' not found.'}

                                

        

class RunningInstance: # Currently running instance, maintains stateful presence between page resets
    def __init__(self):
        # Sets up the API instance
        self.sessions = {}
        self.users = []
        self.u_expire = {}
        self.logger = logging.getLogger('instance_'+LOGMODE)
        self.logger.debug('Instance loaded.')
    
    def _check(self):
        for i in ['sessions','u_expire','logger','new_session','new_user','check_user','get_user_index','edit_name','session_cmd','get_session_info','modify_session','purge_session']:
            if not hasattr(self,i):
                return False
        return True

    def new_session(self,data): # name, password, id, fingerprint, OPTIONAL session data
        # Creates a new session and adds the user that creates it as a DM
        self.logger.debug('Creating session '+data['name']+' with ID '+data['id']+' and DM '+data['fingerprint'])
        if not 'password' in data.keys():
            data['password'] = None
        if 'session' in data.keys():
            self.logger.debug('Loading session from file.')
            self.sessions[data['id']] = {
                'name':data['name'],
                'password':data['password'],
                'instance':Session(self,data['id'],session=data['session'],name=data['name']),
                'expire':datetime.datetime.now()+datetime.timedelta(days=14),
                'users':[
                     {
                        'name':'Dungeon Master',
                        'fingerprint':data['fingerprint'],
                        'type':'dm',
                        'active':True
                    }
                ]
            }
            self.u_expire[data['fingerprint']] = time.time()+30
        else:
            self.logger.debug('Creating session.')
            self.sessions[data['id']] = {
                'name':data['name'],
                'password':data['password'],
                'instance':Session(self,data['id'],name=data['name']),
                'expire':datetime.datetime.now()+datetime.timedelta(days=14),
                'users':[
                     {
                        'name':'Dungeon Master',
                        'fingerprint':data['fingerprint'],
                        'type':'dm',
                        'active':True
                    }
                ]
            }
            self.u_expire[data['fingerprint']] = time.time()+30
        code, r = self.check_user({'fingerprint':data['fingerprint']})
        return code, r
    
    def new_user(self,data): # id, password, name, fingerprint
        self.logger.debug('New user joining session '+data['id']+' with name '+data['name']+' and fingerprint '+data['fingerprint'])
        # Adds a new user to a session if they have the correct password
        if not 'password' in data.keys():
            data['password'] = None
        if data['id'] in self.sessions.keys():
            if data['password'] == self.sessions[data['id']]['password'] or self.sessions[data['id']]['password'] == None:
                self.sessions[data['id']]['users'].append({
                    'name':data['name'],
                    'fingerprint':data['fingerprint'],
                    'type':'pc',
                    'active':True
                })
                self.u_expire[data['fingerprint']] = time.time()+30
                code, r = self.check_user({'fingerprint':data['fingerprint']})
                return code, r
            self.logger.warning('User',data['fingerprint'],'tried to join session',data['id'],'with incorrect password',data['password'])
            return 200, {'code':403}
        self.logger.warning('User',data['fingerprint'],'tried to join nonexistent session with ID',data['id'])
        return 200, {'code':404}
    
    def check_user(self,data): # fingerprint
        # Determines if a user's fingerprint is registered, and returns a session ID if they are.
        for s in list(self.sessions.keys()):
            for u in self.sessions[s]['users']:
                if data['fingerprint'] == u['fingerprint']:
                    return 200, {'found':True,'sid':s,'type':u['type']}
        return 200, {'found':False,'sid':None,'type':None}
    
    def get_user_index(self,sid,fp): # Utility function
        for k in range(len(self.sessions[sid]['users'])):
            if self.sessions[sid]['users'][k]['fingerprint'] == fp:
                return k
        return -1
    
    def edit_name(self,data): # sid, fingerprint, name
        self.logger.debug('User '+data['fingerprint']+' is attempting to change their name to '+data['name'])
        # Edits player name
        if data['sid'] in self.sessions.keys():
            ind = self.get_user_index(data['sid'],data['fingerprint'])
            if ind > -1:
                self.sessions[data['sid']]['users'][ind]['name'] = data['name']
                return 200, {'code':200}
            else:
                self.logger.error('User '+fp+' failed to change name: Not in session.')
                return 200, {'code':404,'reason':'Cannot find that user in the session.'}
        else:
            self.logger.error('User '+fp+' failed to change name: Session does not exist.')
            return 200, {'code':404,'reason':'Cannot find that session.'}
    
    def session_cmd(self,data): # sid, fingerprint, command, args
        if not (data['command'] == 'initiative' and 'check' in data['args'].split('|')):
            self.logger.debug('User '+data['fingerprint']+' sending command '+data['command']+' to session '+data['sid']+' with '+str(len(data['args'].split('|')))+' arguments.')
        # Acts as an intermediary handler between the RunningInstance and the session specific to the user, and handles permissions.
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid']:
            with open('permissions.json','r') as perms:
                pdict = json.loads(perms.read())
                if data['command'] in pdict.keys():
                    if dat['type'] in pdict[data['command']].split(','):
                        return 200, getattr(self.sessions[data['sid']]['instance'],data['command'])(data['fingerprint'],data['args'].split('|'))
                    else:
                        self.logger.warning('User '+data['fingerprint']+' failed to execute '+data['command']+' on session '+data['sid']+' - Access denied to command.')
                        return 200, {'code':403,'reason':'Forbidden: User does not have access to the command "'+data['command']+'".'}
                else:
                    self.logger.warning('User '+data['fingerprint']+' failed to execute '+data['command']+' on session '+data['sid']+' - Command not found.')
                    return 200, {'code':404,'reason':'Not Found: Command "'+data['command']+'" not found.'}
        else:
            self.logger.error('User '+data['fingerprint']+' failed to execute '+data['command']+' on session '+data['sid']+' - Access denied to session.')
            return 200, {'code':403,'reason':'Forbidden: User does not have access to the requested session.'}
    
    def get_session_info(self,data): # sid
        # Get information relating to the session
        if data['sid'] in self.sessions.keys():
            usersDict = {}
            c = 0
            for i in self.sessions[data['sid']]['users']:
                usersDict[i['fingerprint']] = i
                if self.sessions[data['sid']]['users'][c]['fingerprint'] == data['print']:
                    self.u_expire[data['print']] = time.time()+30
                    self.sessions[data['sid']]['users'][c]['active'] = True
                c += 1
            
            self.sessions[data['sid']]['expire'] = datetime.datetime.now()+datetime.timedelta(days=14)

            return 200, {
                'code':200,
                'hasPassword':bool(self.sessions[data['sid']]['password']),
                'name':self.sessions[data['sid']]['name'],
                'users':usersDict,
                'session':self.sessions[data['sid']]['instance'].jsonify()
            }
        else:
            return 200, {'code':404}
    
    def modify_session(self,data): # sid, fingerprint, newname, newpass
        self.logger.debug('User '+data['fingerprint']+' is modifying session '+data['sid'])
        # Modify session information
        if not 'newpass' in data.keys():
            data['newpass'] = None
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid'] and dat['type'] == 'dm':
            self.sessions[data['sid']]['name'] = data['newname']
            self.sessions[data['sid']]['password'] = data['newpass']
            return 200, {'code':200}
        else:
            self.logger.warning('User '+data['fingerprint']+' failed to modify session '+data['sid']+' - No access.')
            return 200, {'code':403,'reason':'You don\'t have access to this feature in this server.'}
    
    def purge_session(self,data): # sid, fingerprint
        self.logger.debug('User '+data['fingerprint']+' is purging session '+data['sid'])
        # Clear session info
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid'] and dat['type'] == 'dm':
            self.sessions[data['sid']]['instance'] = Session()
            return 200, {'code':200}
        else:
            self.logger.error('User '+data['fingerprint']+' failed to purge session '+data['sid']+' - No access.')
            return 200, {'code':403,'reason':'You don\'t have access to this feature in this server.'}



# main code

logging.config.fileConfig('logging.conf')
ROOTLOG = logging.getLogger('root')
ROOTLOG.info('Server started.')
ROOTLOG.info('Stored latest.log to logs/dump/historical_log_'+time.asctime().replace(' ','_').replace(':','_')+'.log')

# Sets up instance
if os.path.exists('state.stor'):
    ROOTLOG.info('Found state.stor file. Loading saved instance.')
    with open('state.stor','rb') as state:
        instance = pickle.load(state)
        if hasattr(instance,'_check'):
            if instance._check:
                ROOTLOG.info('Loaded and checked saved instance.')
            else:
                ROOTLOG.info('Instance check failed, running clean instance.')
                instance = RunningInstance()
        else:
            ROOTLOG.info('Instance check failed, running clean instance.')
            instance = RunningInstance()
else:
    ROOTLOG.info('No state.stor file found. Running clean instance.')
    instance = RunningInstance()

def check_all():
    global instance, ROOTLOG
    while True:
        nse = {}
        for i in instance.sessions.keys():
            if instance.sessions[i]['expire'] <= datetime.datetime.now()+datetime.timedelta(days=14):
                nse[i] = instance.sessions[i]
                for u in range(len(instance.sessions[i]['users'])):
                    if instance.u_expire[instance.sessions[i]['users'][u]['fingerprint']] < time.time() and instance.sessions[i]['users'][u]['active']:
                        instance.sessions[i]['users'][u]['active'] = False
                        ROOTLOG.debug(instance.sessions[i]['users'][u]['fingerprint'] + ' lost connection.')
            else:
                ROOTLOG.info('Killed session'+str(i))

        with open('state.stor','wb') as store:
            pickle.dump(instance,store)

        instance.sessions = nse
        time.sleep(1)

def log_thread():
    global ROOTLOG, MAX_LOG_SIZE
    while True:
        if os.stat(os.path.join('logs','latest.log')).st_size > MAX_LOG_SIZE:
            fname = os.path.join('logs','dump','historical_log_'+time.asctime().replace(' ','_').replace(':','_')+'.log')
            ROOTLOG.info('latest.log exceeded '+str(MAX_LOG_SIZE/1000)+' kilobytes. Moving to logs/dump/historical_log_'+time.asctime().replace(' ','_').replace(':','_')+'.log')
            with open(fname,'w') as f:
                pass
            shutil.copy(os.path.join('logs','latest.log'),fname)
            with open(os.path.join('logs','latest.log'),'w') as f:
                f.write('')
        time.sleep(10)
            

# Activates PyLink instance and sets commands
LINK = PyLink(
    IP,S_PORT,A_PORT,DIR,server_path=os.path.join('api','pylink','server.py'),
    newsession=instance.new_session,
    joinsession=instance.new_user,
    checkuser=instance.check_user,
    scmd=instance.session_cmd,
    gsi=instance.get_session_info,
    editname=instance.edit_name,
    modsession=instance.modify_session,
    purge=instance.purge_session
)

checker = Thread(target=check_all,name='check_thread')
checker.start()
ROOTLOG.info('Launched check_thread.')

logdump = Thread(target=log_thread,name='log_thread')
logdump.start()
ROOTLOG.info('Launched log_thread.')

# Activates servers
ROOTLOG.info('Launching PyLink instance.')
LINK.serve_forever()