import json, os, bs4

with open(os.path.join('compendiums','monsters','__monstermanual.json'),'r') as f:
    dat = json.loads(f.read())
    c = 0
    for m in dat:
        dat[c]['subtype'] = ''
        try:
            traits = m['Traits']
            del m['Traits']
        except:
            traits = ''
        try:
            acts = m['Actions']
            del m['Actions']
        except:
            acts = ''
        try:
            legs = m['Legendary Actions']
            del m['Legendary Actions']
        except:
            legs = ''

        if traits:
            soup = bs4.BeautifulSoup(traits)
            traits = [str(i) for i in soup.children]
            alltraits = []
            prev = []
            for trait in traits:
                if trait.startswith('<p><em><strong>') or trait.startswith('<p><strong>'):
                    if len(prev) == 2:
                        alltraits.append({
                            'name':prev[0],
                            'text':prev[1]
                        })
                    if '</strong></em>' in trait:
                        tsplit = trait.split('</strong></em>')
                    else:
                        tsplit = trait.split('</strong>')
                    name = tsplit[0][15:].strip()
                    desc = tsplit[1].strip()
                    prev = [name,desc]
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
                elif len(prev) == 2:
                    tempsoup = bs4.BeautifulSoup(trait)
                    prev[1] += tempsoup.text
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
            try:
                alltraits.append({
                    'name':prev[0],
                    'text':prev[1]
                })
            except IndexError:
                pass
            dat[c]['trait'] = alltraits
        if acts:
            soup = bs4.BeautifulSoup(acts)
            acts = [str(i) for i in soup.children]
            alltraits = []
            prev = []
            for trait in acts:
                if trait.startswith('<p><em><strong>') or trait.startswith('<p><strong>'):
                    if len(prev) == 2:
                        alltraits.append({
                            'name':prev[0],
                            'text':prev[1]
                        })
                    if '</strong></em>' in trait:
                        tsplit = trait.split('</strong></em>')
                    else:
                        tsplit = trait.split('</strong>')
                    name = tsplit[0][15:].strip()
                    desc = tsplit[1].strip()
                    prev = [name,desc]
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
                elif len(prev) == 2:
                    tempsoup = bs4.BeautifulSoup(trait)
                    prev[1] += tempsoup.text
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
            try:
                alltraits.append({
                    'name':prev[0],
                    'text':prev[1]
                })
            except IndexError:
                pass
            dat[c]['action'] = alltraits
        if legs:
            soup = bs4.BeautifulSoup(legs)
            legs = [str(i) for i in soup.children]
            alltraits = []
            prev = []
            for trait in legs:
                if trait.startswith('<p><em><strong>') or trait.startswith('<p><strong>'):
                    if len(prev) == 2:
                        alltraits.append({
                            'name':prev[0],
                            'text':prev[1]
                        })
                    if '</strong></em>' in trait:
                        tsplit = trait.split('</strong></em>')
                    else:
                        tsplit = trait.split('</strong>')
                    name = tsplit[0][15:].strip()
                    desc = tsplit[1].strip()
                    prev = [name,desc]
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
                elif len(prev) == 2:
                    tempsoup = bs4.BeautifulSoup(trait)
                    prev[1] += tempsoup.text
                    if prev[1].endswith('</p>'):
                        prev[1] = prev[1][:len(prev[1])-4]
            try:
                alltraits.append({
                    'name':prev[0],
                    'text':prev[1]
                })
            except IndexError:
                pass
            dat[c]['legendary'] = alltraits

        c += 1
    

with open(os.path.join('compendiums','monsters','monstermanual.json'),'w') as f:
    json.dump(dat,f,indent=4)
                    


