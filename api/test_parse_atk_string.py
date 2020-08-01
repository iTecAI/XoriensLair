import re
'''action = {
    "name": "Bite",
    "desc": "Melee Weapon Attack: +11 to hit, reach 10 ft., one target. Hit: 17 (2d10 + 6) piercing damage plus 4 (1d8) acid damage.",
    "attack_bonus": 11,
    "damage_dice": "2d10+1d8",
    "damage_bonus": 6
}'''
action = {
    "name": "Slam",
    "desc": "+8 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) damage plus 28 (8d6) fire damage."
}
damage_types = ['acid', 'bludgeoning', 'cold', 'fire', 'force', 'lightning', 'necrotic', 'piercing', 'poison', 'psychic', 'radiant', 'slashing', 'thunder']

def parse(action):
    try:
        if action['desc'].startswith('<i>Melee Weapon Attack:</i>') or action['desc'].startswith('<i>Ranged Weapon Attack:</i>'):
            initial_parse = [i.strip() for i in re.split(r'<i>.{0,50}</i>',action['desc'])[1:]]
            info = {}
            info['attack'] = [i.strip('.,+ ') for i in initial_parse[0].split(', ')][:2]
            info['damage'] = [i.strip('., ') for i in initial_parse[1].split(' plus ')]
            
            ret = action
            ret['attack_bonus'] = int(info['attack'][0].split(' ')[0])
            rollstr = []
            for i in info['damage']:
                rollstr.append(re.split(r'\).{0,1000}',re.split(r'.{0,50}\(',i)[1])[0].replace(' ',''))
            ret['damage_dice'] = '+'.join(rollstr)

            return ret
        else:
            return action
    except:
        return action

def parse_5e(action):
    try:
        if action['desc'].startswith('Melee Weapon Attack: ') or action['desc'].startswith('Ranged Weapon Attack: '):
            damages = re.split(r'.{0,50}: ',action['desc'])[2].split(' plus ')
        else:
            damages = action['desc'].split(' Hit: ')[1].split(' plus ')
        damage_exps = []
        for d in damages:
            damage_exp = {}
            damage_exp['roll'] = re.split(r'\).{0,1000}',re.split(r'.{0,50}\(',d)[1])[0].replace(' ','')
            damage_exp['type'] = 'bludgeoning'
            for dt in damage_types:
                if dt in d:
                    damage_exp['type'] = dt
            damage_exps.append(damage_exp)

        bonus = int(action['desc'].split(': ')[1].split(',')[0].split(' ')[0].lower().strip('+ .,!?qwertyuiopasdfghjklzxcvbnm'))
        action['attack_bonus'] = bonus
        action['damage'] = damage_exps
        return action
    except:
        return action

print(parse_5e(action))