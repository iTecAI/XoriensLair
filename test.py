from api import *
from api.character import Character

c = Character(gurl='1fhyNqPGxePf08ADxiG_XlugZgD-l35nUHNdIJLP-gC4')
print(c['saves']['strengthSave']['value'])
print(c.save('strength'))
print(c['xp'])

g = get('spells')
print(g[0].name)

c = Creature('5e15b15470ee7741669e4e2a')
print(c.intelligence_save)
print(c.speed.walk)
print(c.challenge_rating)
print(c.skills.arcana)
print(c.senses)