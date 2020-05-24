import requests

_token = None
user_id = None


class APIError(Exception):
    pass


def error(res):
    if res.status_code == 200 or res.status_code == 201:
        pass
    else:
        raise APIError('Error {}. The server returned the following message:\n'
                       '{}'.format(res.status_code, res.text))
    return res.json()


def _url(path):
    return 'https://critterdb.com/api' + path


# Creatures
def get_creature(id):
    return error(requests.get(
        url=_url('/creatures/' + id)
    ))


def create_creature(creature):
    return error(requests.post(
        url=_url('/creatures'),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=creature
        ))


def update_creature(id, creature):
    return error(requests.put(
        url=_url('/creatures/' + id),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=creature
        ))


def delete_creature(id):
    return error(requests.delete(
        url=_url('/creatures/' + id),
        headers={'x-access-token': token}
    ))


# Bestiaries
def get_bestiary(id):
    return error(requests.get(
        url=_url('/bestiaries/' + id)
        ))


def get_bestiary_creatures(id):
    return error(requests.get(
        url=_url('/bestiaries/' + id + '/creatures'),
        headers={'x-access-token': token}
        ))


def create_bestiary(bestiary):
    """bestiary should be json with the following structure:
    {
        "name": "your string, required",
        "description": "your string, optional",
        "ownerId": "your userId string, required"
    }
    """
    return error(requests.post(
        url=_url('/bestiaries'),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=bestiary
        ))


def update_bestiary(id, bestiary):
    """bestiary should be JSON as returned by get_bestiary"""
    return error(requests.put(
        url=_url('/bestiaries/' + id),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=bestiary
        ))


def delete_bestiary(id):
    return error(requests.delete(
        url=_url('/bestiaries/' + id),
        headers={'x-access-token': token}
        ))


# Published bestiaries
def search_published(query, page=1):
    """query should be JSON with structure:
    {"name": "your search term"}
    """
    return error(requests.post(
        url=_url('publishedbestiaries/search/' + str(page)),
        body=query
    ))


def like(id):
    return error(requests.post(
        url=_url('publishedbestiaries/' + id + '/likes'),
        headers={'x-access-token': token}
    ))


def unlike(id):
    return error(requests.delete(
        url=_url('publishedbestiaries/' + id + '/likes'),
        headers={'x-access-token': token}
    ))


def favorite(id):
    return error(requests.post(
        url=_url('publishedbestiaries/' + id + '/favorites'),
        headers={'x-access-token': token}
    ))


def unfavorite(id):
    return error(requests.delete(
        url=_url('publishedbestiaries/' + id + '/favorites'),
        headers={'x-access-token': token}
    ))


def get_most_popular():
    return error(requests.get(
        url=_url('/publishedbestiaries/mostpopular')
    ))


def get_recent(page):
    return error(requests.get(
        url=_url('/publishedbestiaries/recent/' + str(page))
    ))


def get_popular(page):
    return error(requests.get(
        url=_url('/publishedbestiaries/popular/' + str(page))
    ))


def get_favorites(page):
    return error(requests.get(
        url=_url('/publishedbestiaries/favorites/' + str(page)),
        headers={'x-access-token': token}
    ))


def get_owned(page):
    return error(requests.get(
        url=_url('/publishedbestiaries/owned/' + str(page)),
        headers={'x-access-token': token}
    ))


def add_comment(id, comment):
    """{
        "text": "comment text",
        "author": "user id"
    }"""
    return error(requests.put(
        url=_url('/publishedbestiaries/' + id + '/comments'),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=comment
    ))


def update_comment(bestiary_id, comment_id, comment):
    return error(requests.put(
        url=_url('/publishedbestiaries/' + bestiary_id
                 + '/comments/' + comment_id),
        headers={'x-access-token': token},
        body=comment
        ))


def delete_comment(bestiary_id, comment_id):
    return error(requests.delete(
        url=_url('/publishedbestiaries/' + bestiary_id
                 + '/comments/' + comment_id),
        headers={'x-access-token': token}
        ))


def get_published_creatures(id, page):
    return error(requests.get(
        url=_url('/publishedbestiaries/' + id + '/creatures')
        ))


def delete_published_creatures(id):
    """Deletes ALL creatures from selected published bestiary."""
    return error(requests.delete(
        url=_url('/publishedbestiaries/' + id),
        headers={'x-access-token': token}
        ))


def get_published(id):
    return error(requests.get(
        url=_url('/publishedbestiaries/' + id)
        ))


def create_published(bestiary):
    return error(requests.post(
        url=_url('/publishedbestiaries'),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=bestiary
        ))


def update_published(id, bestiary):
    return error(requests.put(
        url=_url('/publishedbestiaries' + id),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        body=bestiary
        ))


def delete_published(id):
    return error(requests.delete(
        url=_url('/publishedbestiaries' + id),
        headers={'x-access-token': token}
        ))


# Users
def get_user_bestiaries():
    return error(requests.get(
        url=_url('/users/' + str(user_id) + '/bestiaries'),
        headers={'x-access-token': token}
        ))


def get_user_published(page):
    return error(requests.get(
        url=_url('/users/' + str(user_id) + '/publishedbestiaries/' + page)
        ))


def get_user_creatures(page):
    return error(requests.get(
        url=_url('/users/' + str(user_id) + '/creatures/' + page),
        headers={'x-access-token': token}
        ))


def get_public():
    return error(requests.get(
        url=_url('/users/' + str(user_id) + '/public'),
        headers={'x-access-token': token}
        ))


def search_public(user_dict):
    return error(requests.get(
        url=_url('/users/search'),
        headers={'x-access-token': token,
                 'Content-Type': 'application/json'},
        json=user_dict
        ))

# I'm going to leave user management alone for now. There aren't many legit
# reasons to create or delete users through the API (that I can think of).


# Authentication
def get_current_user():
    return error(requests.get(
        url=_url('/authenticate/user'),
        headers={'x-access-token': token}
    ))


def login(username, password, rememberme=False):
    global token, user_id
    auth_dict = {'username': username,
                 'password': password,
                 'rememberme': rememberme}
    res = requests.post(
        url=_url('/authenticate'),
        headers={'Content-Type': 'application/json'},
        json=auth_dict
    )
    if res.status_code == 200 or res.status_code == 201:
        token = res.text
        user_id = get_current_user()['_id']
    else:
        raise APIError('Error {}. The server returned the following message:\n'
                       '{}'.format(res.status_code, res.text))


# The revokeauthentication endpoint seems to only be to clear auth cookies.
def logout():
    res = requests.get(url=_url('/revokeauthentication'))
    if res.status_code == 200 or res.status_code == 201:
        pass
    else:
        raise APIError('Error {}. The server returned the following message:\n'
                       '{}'.format(res.status_code, res.text))


#Code added by Matteo

#math libs
from fractions import Fraction

class Item: #Item class from accessapi code
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
        self.dct = dct
        for d in dct.keys():
            if type(dct[d]) == dict:
                setattr(self,d,Item(dct[d]))
            elif type(dct[d]) == list:
                setattr(self,d,self.resolve_list(dct[d]))
            else:
                setattr(self,d,dct[d])

def get_mod(score): #code from character to translate a score into a modifier
    modref = {
        '1':-5,
        '2-3':-4,
        '4-5':-3,
        '6-7':-2,
        '8-9':-1,
        '10-11':0,
        '12-13':1,
        '14-15':2,
        '16-17':3,
        '18-19':4,
        '20-21':5,
        '22-23':6,
        '24-25':7,
        '26-27':8,
        '28-29':9,
        '30':10
    }

    for k in modref.keys():
        if str(score) in k.split('-'):
            return modref[k]
    return None

def get_prof_cr(cr): #determines proficiency bonus from challenge rating
    ref = {
        4:2,
        8:3,
        12:4,
        16:5,
        20:6,
        24:7,
        28:8,
        30:9
    } #dict of MM Page 8 proficiency bonuses
    keyref = [4,8,12,16,20,24,28,30] #order of keys to check
    for i in keyref: #check keys
        if cr <= i:
            return ref[i]

def get_skill_ability(skill): #gets ability of specific skill
    skills = (
        ('strength',('athletics')),
        ('dexterity',('acrobatics','sleight_of_hand','stealth')),
        ('constitution',()),
        ('intelligence',('arcana','history','investigation','nature','religion')),
        ('wisdom',('animal_handling','insight','medicine','perception','survival')),
        ('charisma',('deception','intimidation','performance','persuasion'))
    ) #skill reference
    for s in skills: #check all
        if skill in s[1]:
            return s[0]

class Creature: #class to translate CritterDB JSON structure into standard structure based on Open5e
    def __init__(self,ID):
        item = Item(get_creature(ID)) #create item for easy access

        #manual item assignment =======================================================================
        #determine raw attributes
        self.name = item.name
        self.size = item.stats.size
        self.type = str(item.stats.race).lower()
        self.alignment = str(item.stats.alignment).lower()
        self.armor_class = item.stats.armorClass
        self.armor_type = str(item.stats.armorType).lower()
        self.challenge_rating = str(Fraction.from_float(item.stats.challengeRating))
        prof = get_prof_cr(item.stats.challengeRating)

        #determine HP & HD
        self.hit_points = int((item.stats.numHitDie*item.stats.hitDieSize)*0.5)+(get_mod(item.stats.abilityScores.strength)*item.stats.numHitDie)
        self.hit_dice = str(item.stats.numHitDie)+'d'+str(item.stats.hitDieSize)+'+'+str((get_mod(item.stats.abilityScores.strength)*item.stats.numHitDie))
        
        #parse speed string
        speed_dict = {}
        for i in item.stats.speed.split(', '):
            info = i[:len(i)-4].split(' ')
            if len(info) == 1:
                speed_dict['walk'] = int(info[0])
            else:
                speed_dict[info[0]] = int(info[1])
        self.speed = Item(speed_dict)
        for i in item.stats.abilityScores.dct.keys():
            setattr(self,i,item.stats.abilityScores.dct[i])
        
        #generate saves
        saves = {}
        for i in list(item.stats.savingThrows):
            if i.proficient:
                saves[i.ability] = get_mod(item.stats.abilityScores.dct[i.ability]) + prof
            else:
                saves[i.ability] = get_mod(item.stats.abilityScores.dct[i.ability])
        for i in item.stats.abilityScores.dct.keys():
            if i in saves.keys():
                setattr(self,i+'_save',saves[i])
            else:
                setattr(self,i+'_save',None)
        
        #generate skills
        skills = {}
        for i in list(item.stats.skills):
            if i.proficient:
                skills[i.name.lower()] = get_mod(item.stats.abilityScores.dct[get_skill_ability(i.name.lower())]) + prof
            else:
                skills[i.name.lower()] = get_mod(item.stats.abilityScores.dct[get_skill_ability(i.name.lower())])
        self.skills = Item(skills)

        #determine perception bonus
        if 'perception' in skills.keys():
            self.perception = 10 + self.skills.perception
        else:
            self.perception = 10
        
        #assemble senses
        self.senses = ', '.join(list(item.stats.senses))

        #describe abilities
        self.actions = []
        for i in list(item.stats.actions):
            self.actions.append(Item({'name':i.name,'desc':i.description}))
        self.special_abilities = []
        for i in list(item.stats.actions):
            self.special_abilities.append(Item({'name':i.name,'desc':i.description}))
        self.reactions = []
        for i in list(item.stats.actions):
            self.reactions.append(Item({'name':i.name,'desc':i.description}))
        self.legendary_actions = []
        for i in list(item.stats.actions):
            self.legendary_actions.append(Item({'name':i.name,'desc':i.description}))

            

