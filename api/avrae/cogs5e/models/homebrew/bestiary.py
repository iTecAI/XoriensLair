import hashlib
import logging
import re
from math import floor

import aiohttp
import html2text

from api.avrae.cogs5e.funcs.lookupFuncs import compendium
from api.avrae.cogs5e.models.errors import ExternalImportError, NoActiveBrew
from api.avrae.cogs5e.models.homebrew.mixins import CommonHomebrewMixin
from api.avrae.cogs5e.models.monster import Monster, MonsterSpellbook, Trait
from api.avrae.cogs5e.models.sheet.attack import AttackList
from api.avrae.cogs5e.models.sheet.base import BaseStats, Saves, Skills
from api.avrae.cogs5e.models.sheet.spellcasting import SpellbookSpell
from api.avrae.utils.functions import search_and_select

log = logging.getLogger(__name__)

# presented to the hash first - update this when bestiary or monster schema changes
# to invalidate the existing cache of data
BESTIARY_SCHEMA_VERSION = b'1'


class Bestiary(CommonHomebrewMixin):
    def __init__(self, _id, sha256: str, upstream: str,
                 name: str, monsters: list = None, desc: str = None,
                 **_):
        # metadata - should never change
        super().__init__(_id)
        self.sha256 = sha256
        self.upstream = upstream

        # content
        self.name = name
        self.desc = desc
        self._monsters = monsters  # only loaded if needed

    @classmethod
    def from_dict(cls, d):
        if 'monsters' in d:
            d['monsters'] = [Monster.from_bestiary(m) for m in d['monsters']]
        return cls(**d)

    @classmethod
    async def from_ctx(cls, ctx):
        active_bestiary = await cls.active_id(ctx)
        if active_bestiary is None:
            raise NoActiveBrew()
        return await cls.from_id(ctx, active_bestiary)

    @classmethod
    async def from_id(cls, ctx, oid):
        bestiary = await ctx.bot.mdb.bestiaries.find_one({"_id": oid},
                                                         projection={"monsters": False})
        if bestiary is None:
            raise ValueError("Bestiary does not exist")
        return cls.from_dict(bestiary)

    @classmethod
    async def from_critterdb(cls, ctx, url):
        log.info(f"Getting bestiary ID {url}...")
        index = 1
        creatures = []
        sha256_hash = hashlib.sha256()
        sha256_hash.update(BESTIARY_SCHEMA_VERSION)
        async with aiohttp.ClientSession() as session:
            for _ in range(100):  # 100 pages max
                log.info(f"Getting page {index} of {url}...")
                async with session.get(
                        f"http://critterdb.com/api/publishedbestiaries/{url}/creatures/{index}") as resp:
                    if not 199 < resp.status < 300:
                        raise ExternalImportError(
                            "Error importing bestiary: HTTP error. Are you sure the link is right?")
                    try:
                        raw_creatures = await resp.json()
                        sha256_hash.update(await resp.read())
                    except (ValueError, aiohttp.ContentTypeError):
                        raise ExternalImportError("Error importing bestiary: bad data. Are you sure the link is right?")
                    if not raw_creatures:
                        break
                    creatures.extend(raw_creatures)
                    index += 1
            async with session.get(f"http://critterdb.com/api/publishedbestiaries/{url}") as resp:
                try:
                    raw = await resp.json()
                except (ValueError, aiohttp.ContentTypeError):
                    raise ExternalImportError("Error importing bestiary metadata. Are you sure the link is right?")
                name = raw['name']
                desc = raw['description']
                sha256_hash.update(name.encode() + desc.encode())

        # try and find a bestiary by looking up upstream|hash
        # if it exists, return it
        # otherwise commit a new one to the db and return that
        sha256 = sha256_hash.hexdigest()
        log.debug(f"Bestiary hash: {sha256}")
        existing_bestiary = await ctx.bot.mdb.bestiaries.find_one({"upstream": url, "sha256": sha256})
        if existing_bestiary:
            log.info("This bestiary already exists, subscribing")
            existing_bestiary = Bestiary.from_dict(existing_bestiary)
            await existing_bestiary.subscribe(ctx)
            return existing_bestiary

        parsed_creatures = [_monster_factory(c) for c in creatures]
        b = cls(None, sha256, url, name, parsed_creatures, desc)
        await b.write_to_db(ctx)
        await b.subscribe(ctx)
        return b

    async def load_monsters(self, ctx):
        if not self._monsters:
            bestiary = await ctx.bot.mdb.bestiaries.find_one({"_id": self.id}, projection=['monsters'])
            self._monsters = [Monster.from_bestiary(m) for m in bestiary['monsters']]
        return self._monsters

    @property
    def monsters(self):
        if self._monsters is None:
            raise AttributeError("load_monsters() must be called before accessing bestiary monsters.")
        return self._monsters

    async def write_to_db(self, ctx):
        """Writes a new bestiary object to the database."""
        assert self._monsters is not None
        monsters = [m.to_dict() for m in self._monsters]

        data = {
            "sha256": self.sha256, "upstream": self.upstream,
            "name": self.name, "desc": self.desc, "monsters": monsters
        }

        result = await ctx.bot.mdb.bestiaries.insert_one(data)
        self.id = result.inserted_id

    async def delete(self, ctx):
        await ctx.bot.mdb.bestiaries.delete_one({"_id": self.id})
        await self.remove_all_tracking(ctx)

    # ==== subscriber helpers ====
    @staticmethod
    def sub_coll(ctx):
        return ctx.bot.mdb.bestiary_subscriptions

    async def set_server_active(self, ctx):
        """
        Sets the object as active for the contextual guild.
        This override is here because bestiaries' server active docs need a provider id.
        """
        sub_doc = {"type": "server_active", "subscriber_id": ctx.guild.id,
                   "object_id": self.id, "provider_id": ctx.author.id}
        await self.sub_coll(ctx).insert_one(sub_doc)

    async def unsubscribe(self, ctx):
        """The unsubscribe operation for bestiaries actually acts as a delete operation."""
        # unsubscribe me
        await super().unsubscribe(ctx)

        # remove all server subs that I provide
        await self.sub_coll(ctx).delete_many(
            {"type": "server_active", "provider_id": ctx.author.id, "object_id": self.id}
        )

        # if no one is subscribed to this bestiary anymore, delete it.
        if not await self.num_subscribers(ctx):
            await self.delete(ctx)

    @staticmethod
    async def user_bestiaries(ctx):
        """Returns an async iterator of partial Bestiary objects that the user has imported."""
        async for b in Bestiary.my_sub_ids(ctx):
            yield await Bestiary.from_id(ctx, b)

    @staticmethod
    async def server_bestiaries(ctx):
        """Returns an async iterator of partial Bestiary objects that are active on the server."""
        async for b in Bestiary.guild_active_ids(ctx):
            yield await Bestiary.from_id(ctx, b)

    # ==== bestiary-specific database helpers ====
    async def server_subscriptions(self, ctx):
        """Returns a list of server ids (ints) representing server subscriptions supplied by the contextual author.
        Mainly used to determine what subscriptions should be carried over to a new bestiary when updated."""
        subs = ctx.bot.mdb.bestiary_subscriptions.find(
            {"type": "server_active", "object_id": self.id, "provider_id": ctx.author.id})
        return [s['subscriber_id'] async for s in subs]

    async def add_server_subscriptions(self, ctx, serv_ids):
        """Subscribes a list of servers to this bestiary."""
        existing = await ctx.bot.mdb.bestiary_subscriptions.find(
            {"type": "server_active", "subscriber_id": {"$in": serv_ids}}
        ).to_list(None)
        existing = {e['subscriber_id'] for e in existing}
        sub_docs = [{"type": "server_active", "subscriber_id": serv_id,
                     "object_id": self.id, "provider_id": ctx.author.id} for serv_id in serv_ids if
                    serv_id not in existing]
        if sub_docs:
            await ctx.bot.mdb.bestiary_subscriptions.insert_many(sub_docs)

    @staticmethod
    async def num_user(ctx):
        """Returns the number of bestiaries a user has imported."""
        return await ctx.bot.mdb.bestiary_subscriptions.count_documents(
            {"type": "subscribe", "subscriber_id": ctx.author.id}
        )

    async def get_server_sharer(self, ctx):
        """Returns the user ID of the user who shared this bestiary with the server."""
        sub = await ctx.bot.mdb.bestiary_subscriptions.find_one(
            {"type": "server_active", "object_id": self.id}
        )
        if sub is None:
            raise ValueError("This bestiary is not active on this server.")
        return sub.get("provider_id")


async def select_bestiary(ctx, name):
    user_bestiaries = []
    async for b in Bestiary.user_bestiaries(ctx):
        user_bestiaries.append(b)
    if not user_bestiaries:
        raise NoActiveBrew()

    bestiary = await search_and_select(ctx, user_bestiaries, name, key=lambda b: b.name,
                                       selectkey=lambda b: f"{b.name} (`{b.upstream})`")
    return bestiary


# critterdb -> bestiary helpers
AVRAE_ATTACK_OVERRIDES_RE = re.compile(r'<avrae hidden>(.*?)\|([+-]?\d*)\|(.*?)</avrae>', re.IGNORECASE)
ATTACK_RE = re.compile(r'(?:<i>)?(?:\w+ ){1,4}Attack:(?:</i>)? ([+-]?\d+) to hit, .*?(?:<i>)?'
                       r'Hit:(?:</i>)? [+-]?\d+ \((.+?)\) (\w+) damage[., ]??'
                       r'(?:in melee, or [+-]?\d+ \((.+?)\) (\w+) damage at range[,.]?)?'
                       r'(?: or [+-]?\d+ \((.+?)\) (\w+) damage .*?[.,]?)?'
                       r'(?: (?:plus|and) [+-]?\d+ \((.+?)\) (\w+) damage.)?', re.IGNORECASE)
JUST_DAMAGE_RE = re.compile(r'[+-]?\d+ \((.+?)\) (\w+) damage', re.IGNORECASE)


def spaced_to_camel(spaced):
    return re.sub(r"\s+(\w)", lambda m: m.group(1).upper(), spaced.lower())


def _monster_factory(data):
    ability_scores = BaseStats(data['stats']['proficiencyBonus'] or 0,
                               data['stats']['abilityScores']['strength'] or 10,
                               data['stats']['abilityScores']['dexterity'] or 10,
                               data['stats']['abilityScores']['constitution'] or 10,
                               data['stats']['abilityScores']['intelligence'] or 10,
                               data['stats']['abilityScores']['wisdom'] or 10,
                               data['stats']['abilityScores']['charisma'] or 10)
    cr = {0.125: '1/8', 0.25: '1/4', 0.5: '1/2'}.get(data['stats']['challengeRating'],
                                                     str(data['stats']['challengeRating']))
    num_hit_die = data['stats']['numHitDie']
    hit_die_size = data['stats']['hitDieSize']
    con_by_level = num_hit_die * ability_scores.get_mod('con')
    hp = floor(((hit_die_size + 1) / 2) * num_hit_die) + con_by_level
    hitdice = f"{num_hit_die}d{hit_die_size} + {con_by_level}"

    proficiency = data['stats']['proficiencyBonus']
    if proficiency is None:
        raise ExternalImportError(f"Monster's proficiency bonus is nonexistent ({data['name']}).")

    skills = Skills.default(ability_scores)
    skill_updates = {}
    for skill in data['stats']['skills']:
        name = spaced_to_camel(skill['name'])
        if skill['proficient']:
            mod = skills[name].value + proficiency
        else:
            mod = skill.get('value')
        if mod is not None:
            skill_updates[name] = mod
    skills.update(skill_updates)

    saves = Saves.default(ability_scores)
    save_updates = {}
    for save in data['stats']['savingThrows']:
        name = save['ability'].lower() + 'Save'
        if save['proficient']:
            mod = saves.get(name).value + proficiency
        else:
            mod = save.get('value')
        if mod is not None:
            save_updates[name] = mod
    saves.update(save_updates)

    attacks = []
    traits, atks = parse_critterdb_traits(data, 'additionalAbilities')
    attacks.extend(atks)
    actions, atks = parse_critterdb_traits(data, 'actions')
    attacks.extend(atks)
    reactions, atks = parse_critterdb_traits(data, 'reactions')
    attacks.extend(atks)
    legactions, atks = parse_critterdb_traits(data, 'legendaryActions')
    attacks.extend(atks)

    attacks = AttackList.from_dict(attacks)
    spellcasting = parse_critterdb_spellcasting(traits, ability_scores)

    return Monster(data['name'], data['stats']['size'], data['stats']['race'], data['stats']['alignment'],
                   data['stats']['armorClass'], data['stats']['armorType'], hp, hitdice, data['stats']['speed'],
                   ability_scores, cr, data['stats']['experiencePoints'], None,
                   ', '.join(data['stats']['senses']), data['stats']['damageVulnerabilities'],
                   data['stats']['damageResistances'], data['stats']['damageImmunities'],
                   data['stats']['conditionImmunities'], saves, skills,
                   data['stats']['languages'], traits, actions, reactions, legactions,
                   data['stats']['legendaryActionsPerRound'], True, 'homebrew', attacks,
                   data['flavor']['nameIsProper'], data['flavor']['imageUrl'],
                   spellcasting=spellcasting)


def parse_critterdb_traits(data, key):
    traits = []
    attacks = []
    for trait in data['stats'][key]:
        name = trait['name']
        raw = trait['description']

        overrides = list(AVRAE_ATTACK_OVERRIDES_RE.finditer(raw))
        raw_atks = list(ATTACK_RE.finditer(raw))
        raw_damage = list(JUST_DAMAGE_RE.finditer(raw))

        filtered = AVRAE_ATTACK_OVERRIDES_RE.sub('', raw)
        desc = '\n'.join(html2text.html2text(text, bodywidth=0).strip() for text in filtered.split('\n')).strip()

        if overrides:
            for override in overrides:
                attacks.append({'name': override.group(1) or name,
                                'attackBonus': override.group(2) or None, 'damage': override.group(3) or None,
                                'details': desc})
        elif raw_atks:
            for atk in raw_atks:
                if atk.group(6) and atk.group(7):  # versatile
                    damage = f"{atk.group(6)}[{atk.group(7)}]"
                    if atk.group(8) and atk.group(8):  # bonus damage
                        damage += f"+{atk.group(8)}[{atk.group(9)}]"
                    attacks.append(
                        {'name': f"2 Handed {name}", 'attackBonus': atk.group(1).lstrip('+'), 'damage': damage,
                         'details': desc})
                if atk.group(4) and atk.group(5):  # ranged
                    damage = f"{atk.group(4)}[{atk.group(5)}]"
                    if atk.group(8) and atk.group(8):  # bonus damage
                        damage += f"+{atk.group(8)}[{atk.group(9)}]"
                    attacks.append({'name': f"Ranged {name}", 'attackBonus': atk.group(1).lstrip('+'), 'damage': damage,
                                    'details': desc})
                damage = f"{atk.group(2)}[{atk.group(3)}]"
                if atk.group(8) and atk.group(9):  # bonus damage
                    damage += f"+{atk.group(8)}[{atk.group(9)}]"
                attacks.append(
                    {'name': name, 'attackBonus': atk.group(1).lstrip('+'), 'damage': damage, 'details': desc})
        else:
            for dmg in raw_damage:
                damage = f"{dmg.group(1)}[{dmg.group(2)}]"
                attacks.append({'name': name, 'attackBonus': None, 'damage': damage, 'details': desc})

        traits.append(Trait(name, desc))
    return traits, attacks


def parse_critterdb_spellcasting(traits, base_stats):
    known_spells = []
    will_spells = []
    daily_spells = {}
    usual_dc = (0, 0)  # dc, number of spells using dc
    usual_sab = (0, 0)  # same thing
    usual_cab = (0, 0)
    caster_level = 1
    slots = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0}

    for trait in traits:
        if not 'Spellcasting' in trait.name:
            continue
        desc = trait.desc

        type_match = re.search(r'spellcasting ability is (\w+) \(spell save DC (\d+), [+\-](\d+) to hit', desc)
        type_dc = int(type_match.group(2)) if type_match else None
        type_sab = int(type_match.group(3)) if type_match else None
        type_casting_ability = base_stats.get_mod(type_match.group(1)) if type_match else None
        type_caster_level_match = re.search(r'(\d+)[stndrh]{2}-level', desc)
        caster_level = max(caster_level,
                           int(type_caster_level_match.group(1))) if type_caster_level_match else caster_level
        type_spells = []

        def extract_spells(text):
            extracted = []
            spell_names = text.split(', ')
            for name in spell_names:
                s = name.strip('* _')

                try:
                    real_name = next(sp for sp in compendium.spells if sp.name.lower() == s).name
                    strict = True
                except StopIteration:
                    real_name = s
                    strict = False

                extracted.append(
                    SpellbookSpell(real_name, strict=strict, dc=type_dc, sab=type_sab, mod=type_casting_ability))
            type_spells.extend(extracted)
            return extracted

        for type_leveled_spells in re.finditer(
                r"(?:"
                r"(?:(?P<level>\d)[stndrh]{2}\slevel \((?P<slots>\d+) slots\))"
                r"|(?:Cantrip \(at will\))): "
                r"(?P<spells>.+)$",
                desc, re.MULTILINE):
            extract_spells(type_leveled_spells.group("spells"))
            if type_leveled_spells.group("level") and type_leveled_spells.group("slots"):
                slots[type_leveled_spells.group("level")] = int(type_leveled_spells.group("slots"))

        for type_will_spells in re.finditer(r"At will: (?P<spells>.+)$", desc, re.MULTILINE):
            extracted = extract_spells(type_will_spells.group("spells"))
            will_spells.extend(s.name for s in extracted)

        for type_daily_spells in re.finditer(r"(?P<times>\d+)/day: (?P<spells>.+)$", desc, re.MULTILINE):
            extracted = extract_spells(type_daily_spells.group("spells"))
            times_per_day = int(type_daily_spells.group("times"))
            for ts in extracted:
                daily_spells[ts.name] = times_per_day

        known_spells.extend(type_spells)
        if type_dc and (len(type_spells) > usual_dc[1] or not usual_dc[0]):
            usual_dc = (type_dc, len(type_spells))
        if type_sab and (len(type_spells) > usual_sab[1] or not usual_sab[0]):
            usual_sab = (type_sab, len(type_spells))
        if len(type_spells) > usual_cab[1] or not usual_cab[0]:
            usual_cab = (type_casting_ability, len(type_spells))

    spellbook = MonsterSpellbook(
        slots=slots, max_slots=slots, spells=known_spells, dc=usual_dc[0], sab=usual_sab[0],
        caster_level=caster_level, spell_mod=usual_cab[0], at_will=will_spells, daily=daily_spells
    )

    for spell in spellbook.spells:  # remove redundant data
        if spell.dc == spellbook.dc:
            spell.dc = None
        if spell.sab == spellbook.sab:
            spell.sab = None
        if spell.mod == spellbook.spell_mod:
            spell.mod = None

    log.debug(f"Critter spellbook: {spellbook.to_dict()}")
    return spellbook
