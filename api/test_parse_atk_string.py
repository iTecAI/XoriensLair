import re
action = {
    'name':'Tail',
    'desc':'<i>Melee Weapon Attack:</i> +15 to hit, reach 15 ft., one target. <i>Hit:</i> 20 (2d10 + 9) piercing damage plus 14 (4d6) fire damage.'
}

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

print(parse(action))