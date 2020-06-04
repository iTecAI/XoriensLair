from api import *
import os
import base64
import json
import datetime, time
from threading import Thread
from hashlib import sha256
from random import  random

# options
IP = '192.168.86.36'
S_PORT = 1022
A_PORT = 1023
DIR = os.path.join(os.getcwd(),'client/')

class Session:
    def __init__(self,session=None):
        if session:
            print(session)
            session = json.loads(session)
            self.maps = session['maps']
            self.characters = session['characters']
        else:
            self.maps = []
            self.characters = {}

    def jsonify(self):
        ndct = {}
        for k in self.characters.keys():
            ndct[k] = json.loads(self.characters[k].to_json())

        return {
            'maps':self.maps,
            'characters':ndct
        }
    
    def save(self,fp,args): # No arguments
        return {'save':self.jsonify()}

    def load_sheet(self,fp,args): # [URL or Beyond ID]
        url = args[0]
        if url.startswith('https://docs.google.com/spreadsheets'):
            char = Character(gurl=url.split('/')[5])
        elif url.startswith('{'):
            char = Character(_json=url)
        else:
            char = Character(ddbid=url)
        self.characters[fp] = char
        return {'code':200}
    
    def load_map(self,fp,args): # [Data URL, # Rows, # Columns, Feet/grid square]
        url = args[0]
        self.maps.append({
            'image': url,
            'id': sha256(str(time.time()*random()).encode('utf-8')).hexdigest(),
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
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == _id:
                del self.maps[i]
                return {'code':200}
        return {'code':404,'reason':'Map not found.'}
    
    def modify_map(self,fp,args): # [Map ID, # Rows, # Columns, Feet/square, X, Y, Active]
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['grid_data'] = {
                    'rows':args[1],
                    'columns':args[2],
                    'size':args[3]
                }
                self.maps[i]['active'] = args[4]
                return {'code':200}
        return {'code':404,'reason':'Map not found.'}
    
    def obscure(self,fp,args): # [Map ID, Top Corner X, Top Corner Y, Width, Height, Obscuration ID]
        args[1] = float(args[1])
        args[2] = float(args[2])
        args[3] = float(args[3])
        args[4] = float(args[4])
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['obscuration'][args[5]] = [args[1],args[2],args[3],args[4]]
                return {'code':200}
        return {'code':404,'reason':'Map not found.'}
    
    def remove_obscure(self,fp,args): # [Map ID, Obscuration ID]
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if args[1] in self.maps[i]['obscuration'].keys():
                    del self.maps[i]['obscuration'][args[1]]
                    return {'code':200}
                else:
                    return {'code':404,'reason':'Obscure not found.'}
        return {'code':404,'reason':'Map not found.'}
    
    def activate_pc(self,fp,args): # [Map ID, Icon Name or Data URL, X, Y]
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                self.maps[i]['characters'][fp] = {
                    'name':self.characters[fp]['name'],
                    'pos':[int(args[2]),int(args[3])],
                    'icon':args[1]
                }
                return {'code':200}
        return {'code':404,'reason':'Map not found.'}
    
    def move_pc(self,fp,args): # [Map ID, X, Y]
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if fp in self.maps[i]['characters'].keys():
                    self.maps[i]['characters'][fp]['pos'] = [int(float(args[1])),int(float(args[2]))]
                    return {'code':200}
                else:
                    return {'code':404,'reason':'Character not found.'}
        return {'code':404,'reason':'Map not found.'}
    
    def deactivate_pc(self,fp,args): # [Map ID]
        for i in range(len(self.maps)):
            if self.maps[i]['id'] == args[0]:
                if fp in self.maps[i]['characters'].keys():
                    del self.maps[i]['characters'][fp]
                    return {'code':200}
                else:
                    return {'code':404,'reason':'Character not found.'}
        return {'code':404,'reason':'Map not found.'}

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
        for a in args:
            sp = a.split(',')
            arguments.append(tuple(sp))
        rs = 'get(restype,'+','.join([n[0]+'="'+n[1]+'"' for n in arguments])+')'
        results = eval(rs)
        return {'code':200,'result':json.dumps({'data':[i.json for i in results]})}

        

class RunningInstance: # Currently running instance, maintains stateful presence between page resets
    def __init__(self):
        # Sets up the API instance
        self.sessions = {}
        self.users = []

    def new_session(self,data): # name, password, id, fingerprint, OPTIONAL session data
        # Creates a new session and adds the user that creates it as a DM
        if not 'password' in data.keys():
            data['password'] = None
        if 'session' in data.keys():
            print(data)
            self.sessions[data['id']] = {
                'name':data['name'],
                'password':data['password'],
                'instance':Session(session=data['session']),
                'expire':datetime.datetime.now()+datetime.timedelta(days=14),
                'users':[
                     {
                        'name':'Dungeon Master',
                        'fingerprint':data['fingerprint'],
                        'type':'dm'
                    }
                ]
            }
        else:
            self.sessions[data['id']] = {
                'name':data['name'],
                'password':data['password'],
                'instance':Session(),
                'expire':datetime.datetime.now()+datetime.timedelta(days=14),
                'users':[
                     {
                        'name':'Dungeon Master',
                        'fingerprint':data['fingerprint'],
                        'type':'dm'
                    }
                ]
            }
        code, r = self.check_user({'fingerprint':data['fingerprint']})
        return code, r
    
    def new_user(self,data): # id, password, name, fingerprint
        # Adds a new user to a session if they have the correct password
        if not 'password' in data.keys():
            data['password'] = None
        if data['id'] in self.sessions.keys():
            if data['password'] == self.sessions[data['id']]['password'] or self.sessions[data['id']]['password'] == None:
                self.sessions[data['id']]['users'].append({
                    'name':data['name'],
                    'fingerprint':data['fingerprint'],
                    'type':'pc'
                })
                code, r = self.check_user({'fingerprint':data['fingerprint']})
                return code, r
            return 200, {'code':403}
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
        # Edits player name
        print(data)
        if data['sid'] in self.sessions.keys():
            ind = self.get_user_index(data['sid'],data['fingerprint'])
            if ind > -1:
                self.sessions[data['sid']]['users'][ind]['name'] = data['name']
                return 200, {'code':200}
            else:
                return 200, {'code':404,'reason':'Cannot find that user in the session.'}
        else:
            return 200, {'code':404,'reason':'Cannot find that session.'}
    
    def session_cmd(self,data): # sid, fingerprint, command, args
        # Acts as an intermediary handler between the RunningInstance and the session specific to the user, and handles permissions.
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid']:
            with open('permissions.json','r') as perms:
                pdict = json.loads(perms.read())
                if data['command'] in pdict.keys():
                    if dat['type'] in pdict[data['command']].split(','):
                        return 200, getattr(self.sessions[data['sid']]['instance'],data['command'])(data['fingerprint'],data['args'].split('|'))
                    else:
                        return 200, {'code':403,'reason':'Forbidden: User does not have access to the command "'+data['command']+'".'}
                else:
                    return 200, {'code':404,'reason':'Not Found: Command "'+data['command']+'" not found.'}
        else:
            return 200, {'code':403,'reason':'Forbidden: User does not have access to the requested session.'}
    
    def get_session_info(self,data): # sid
        # Get information relating to the session
        if data['sid'] in self.sessions.keys():
            usersDict = {}
            for i in self.sessions[data['sid']]['users']:
                usersDict[i['fingerprint']] = i
            
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
        # Modify session information
        if not 'newpass' in data.keys():
            data['newpass'] = None
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid'] and dat['type'] == 'dm':
            self.sessions[data['sid']]['name'] = data['newname']
            self.sessions[data['sid']]['password'] = data['newpass']
            return 200, {'code':200}
        else:
            return 200, {'code':403,'reason':'You don\'t have access to this feature in this server.'}
    
    def purge_session(self,data): # sid, fingerprint
        # Clear session info
        code, dat = self.check_user({'fingerprint':data['fingerprint']})
        if dat['sid'] == data['sid'] and dat['type'] == 'dm':
            self.sessions[data['sid']]['instance'] = Session()
            return 200, {'code':200}
        else:
            return 200, {'code':403,'reason':'You don\'t have access to this feature in this server.'}



# main code

# Sets up instance
instance = RunningInstance()

def check_all():
    global instance
    while True:
        nse = {}
        for i in instance.sessions.keys():
            if instance.sessions[i]['expire'] <= datetime.datetime.now()+datetime.timedelta(days=14):
                nse[i] = instance.sessions[i]
        instance.sessions = nse
        time.sleep(60)
            

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

# Activates servers
LINK.serve_forever()