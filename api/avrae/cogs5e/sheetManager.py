"""
Created on Jan 19, 2017

@author: andrew
"""
import asyncio
import logging
import re
import traceback

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from api.avrae.cogs5e.funcs import attackutils, checkutils, targetutils
from api.avrae.cogs5e.funcs.scripting import helpers
from api.avrae.cogs5e.models.character import Character
from api.avrae.cogs5e.models.embeds import EmbedWithCharacter
from api.avrae.cogs5e.models.errors import ExternalImportError
from api.avrae.cogs5e.models.sheet.attack import Attack
from api.avrae.cogs5e.sheets.beyond import BeyondSheetParser
from api.avrae.cogs5e.sheets.dicecloud import DicecloudParser
from api.avrae.cogs5e.sheets.gsheet import GoogleSheet
from api.avrae.utils.argparser import argparse
from api.avrae.utils.constants import SKILL_NAMES
from api.avrae.utils.functions import auth_and_chan, get_positivity, list_get, try_delete
from api.avrae.utils.functions import extract_gsheet_id_from_url, generate_token, search_and_select
from api.avrae.utils.user_settings import CSetting

log = logging.getLogger(__name__)

CHARACTER_SETTINGS = {
    "color": CSetting("color", "hex", default="random", display_func=lambda val: f"#{val:06X}", min_=0,
                      max_=0xffffff),
    "criton": CSetting("criton", "number", description="crit range", default=20,
                       display_func=lambda val: f"{val}-20", min_=1, max_=20),
    "reroll": CSetting("reroll", "number", min_=1, max_=20),
    "srslots": CSetting("srslots", "boolean", description="short rest slots", default='disabled',
                        display_func=lambda val: 'enabled' if val else 'disabled'),
    "embedimage": CSetting("embedimage", "boolean", description="embed image", default='disabled',
                           display_func=lambda val: 'enabled' if val else 'disabled'),
    "critdice": CSetting("critdice", "number", description="extra crit dice", default=0),
    "talent": CSetting("talent", "boolean", description="reliable talent", default='disabled',
                       display_func=lambda val: 'enabled' if val else 'disabled')
}


class SheetManager(commands.Cog):
    """
    Commands to load a character sheet into Avrae, and supporting commands to modify the character, as well as basic macros.
    """

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def new_arg_stuff(args, ctx, character):
        args = await helpers.parse_snippets(args, ctx)
        args = await character.parse_cvars(args, ctx)
        args = argparse(args)
        return args

    @commands.group(aliases=['a'], invoke_without_command=True)
    async def attack(self, ctx, atk_name=None, *, args: str = ''):
        """Rolls an attack for the current active character.
        __Valid Arguments__
        -t "<target>" - Sets targets for the attack. You can pass as many as needed. Will target combatants if channel is in initiative.
        -t "<target>|<args>" - Sets a target, and also allows for specific args to apply to them. (e.g, -t "OR1|hit" to force the attack against OR1 to hit)

        *adv/dis*
        *ea* (Elven Accuracy double advantage)
        
        -ac [target ac]
        -t [target]
        
        *-b* [to hit bonus]
        -criton [a number to crit on if rolled on or above]
        *-d* [damage bonus]
        *-c* [damage bonus on crit]
        -rr [times to reroll]
        *-mi* [minimum weapon dice roll]
        
        *-resist* [damage resistance]
        *-immune* [damage immunity]
        *-vuln* [damage vulnerability]
        *-neutral* [damage non-resistance]
        
        *hit* (automatically hits)
        *miss* (automatically misses)
        *crit* (automatically crit)
        *max* (deals max damage)

        -h (hides name and rolled values)
        -phrase [flavor text]
        -title [title] *note: [name] and [aname] will be replaced automatically*
        -thumb [url]
        -f "Field Title|Field Text" (see !embed)
        [user snippet]

        An italicized argument means the argument supports ephemeral arguments - e.g. `-d1` applies damage to the first hit, `-b1` applies a bonus to one attack, and so on."""
        if atk_name is None:
            return await ctx.invoke(self.attack_list)

        char: Character = await Character.from_ctx(ctx)
        args = await self.new_arg_stuff(args, ctx, char)

        caster, targets, combat = await targetutils.maybe_combat(ctx, char, args)
        attack = await search_and_select(ctx, caster.attacks, atk_name, lambda a: a.name)

        embed = EmbedWithCharacter(char, name=False)
        await attackutils.run_attack(ctx, embed, args, caster, attack, targets, combat)

        await ctx.send(embed=embed)
        await try_delete(ctx.message)

    @attack.command(name="list")
    async def attack_list(self, ctx):
        """Lists the active character's attacks."""
        char: Character = await Character.from_ctx(ctx)
        atk_str = char.attacks.build_str(char)
        if len(atk_str) > 1000:
            atk_str = f"{atk_str[:1000]}\n[...]"
        return await ctx.send(f"{char.name}'s attacks:\n{atk_str}")

    @attack.command(name="add", aliases=['create'])
    async def attack_add(self, ctx, name, *args):
        """
        Adds an attack to the active character.
        __Arguments__
        -d [damage]: How much damage the attack should do.
        -b [to-hit]: The to-hit bonus of the attack.
        -desc [description]: A description of the attack.
        """
        character: Character = await Character.from_ctx(ctx)
        parsed = argparse(args)

        attack = Attack.new(name, bonus_calc=parsed.join('b', '+'),
                            damage_calc=parsed.join('d', '+'), details=parsed.join('desc', '\n'))

        conflict = next((a for a in character.overrides.attacks if a.name.lower() == attack.name.lower()), None)
        if conflict:
            character.overrides.attacks.remove(conflict)
        character.overrides.attacks.append(attack)
        await character.commit(ctx)

        out = f"Created attack {attack.name}!"
        if conflict:
            out += f" Removed a duplicate attack."
        await ctx.send(out)

    @attack.command(name="delete", aliases=['remove'])
    async def attack_delete(self, ctx, name):
        """
        Deletes an attack override.
        """
        character: Character = await Character.from_ctx(ctx)
        attack = await search_and_select(ctx, character.overrides.attacks, name, lambda a: a.name)
        character.overrides.attacks.remove(attack)
        await character.commit(ctx)
        await ctx.send(f"Okay, deleted attack {attack.name}.")

    @commands.command(aliases=['s'])
    async def save(self, ctx, skill, *args):
        """Rolls a save for your current active character.
        __Valid Arguments__
        *adv/dis*
        *-b [conditional bonus]*
        -phrase [flavor text]
        -title [title] *note: [name] and [sname] will be replaced automatically*
        -image [image URL]
        -dc [dc] (does not apply to Death Saves)
        -rr [iterations] (does not apply to Death Saves)

        An italicized argument means the argument supports ephemeral arguments - e.g. `-b1` applies a bonus to one save.
        """
        if skill == 'death':
            ds_cmd = self.bot.get_command('game deathsave')
            if ds_cmd is None:
                return await ctx.send("Error: GameTrack cog not loaded.")
            return await ctx.invoke(ds_cmd, *args)

        char: Character = await Character.from_ctx(ctx)

        embed = EmbedWithCharacter(char, name=False)

        args = await self.new_arg_stuff(args, ctx, char)

        # halfling luck
        args['ro'] = char.get_setting('reroll')

        checkutils.run_save(skill, char, args, embed)

        if args.last('image') is not None:
            embed.set_thumbnail(url=args.last('image'))

        # send
        await ctx.send(embed=embed)
        await try_delete(ctx.message)

    @commands.command(aliases=['c'])
    async def check(self, ctx, check, *args):
        """Rolls a check for your current active character.
        __Valid Arguments__
        *adv/dis*
        *-b [conditional bonus]*
        -phrase [flavor text]
        -title [title] *note: [name] and [cname] will be replaced automatically*
        -dc [dc]
        -mc [minimum roll]
        -rr [iterations]
        str/dex/con/int/wis/cha (different skill base; e.g. Strength (Intimidation))

        An italicized argument means the argument supports ephemeral arguments - e.g. `-b1` applies a bonus to one check.
        """
        char: Character = await Character.from_ctx(ctx)
        skill_key = await search_and_select(ctx, SKILL_NAMES, check, lambda s: s)

        embed = EmbedWithCharacter(char, False)
        skill = char.skills[skill_key]

        args = await self.new_arg_stuff(args, ctx, char)

        # reliable talent (#654)
        rt = char.get_setting('talent', 0) and skill.prof >= 1
        args['mc'] = args.get('mc') or 10 * rt

        # halfling luck
        args['ro'] = char.get_setting('reroll')

        checkutils.run_check(skill_key, char, args, embed)

        if args.last('image') is not None:
            embed.set_thumbnail(url=args.last('image'))

        await ctx.send(embed=embed)
        await try_delete(ctx.message)

    @commands.group(invoke_without_command=True)
    async def desc(self, ctx):
        """Prints or edits a description of your currently active character."""
        char: Character = await Character.from_ctx(ctx)

        desc = char.description
        if not desc:
            desc = 'No description available.'

        if len(desc) > 2048:
            desc = desc[:2044] + '...'
        elif len(desc) < 2:
            desc = 'No description available.'

        embed = EmbedWithCharacter(char, name=False)
        embed.title = char.name
        embed.description = desc

        await ctx.send(embed=embed)
        await try_delete(ctx.message)

    @desc.command(name='update', aliases=['edit'])
    async def edit_desc(self, ctx, *, desc):
        """Updates the character description."""
        char: Character = await Character.from_ctx(ctx)
        char.overrides.desc = desc
        await char.commit(ctx)
        await ctx.send("Description updated!")

    @desc.command(name='remove', aliases=['delete'])
    async def remove_desc(self, ctx):
        """Removes the character description, returning to the default."""
        char: Character = await Character.from_ctx(ctx)
        char.overrides.desc = None
        await char.commit(ctx)
        await ctx.send(f"Description override removed!")

    @commands.group(invoke_without_command=True)
    async def portrait(self, ctx):
        """Shows or edits the image of your currently active character."""
        char: Character = await Character.from_ctx(ctx)

        if not char.image:
            return await ctx.send("No image available.")

        embed = discord.Embed()
        embed.title = char.name
        embed.colour = char.get_color()
        embed.set_image(url=char.image)

        await ctx.send(embed=embed)
        await try_delete(ctx.message)

    @portrait.command(name='update', aliases=['edit'])
    async def edit_portrait(self, ctx, *, url):
        """Updates the character portrait."""
        char: Character = await Character.from_ctx(ctx)
        char.overrides.image = url
        await char.commit(ctx)
        await ctx.send("Portrait updated!")

    @portrait.command(name='remove', aliases=['delete'])
    async def remove_portrait(self, ctx):
        """Removes the character portrait, returning to the default."""
        char: Character = await Character.from_ctx(ctx)
        char.overrides.image = None
        await char.commit(ctx)
        await ctx.send(f"Portrait override removed!")

    @commands.command(hidden=True)  # hidden, as just called by token command
    async def playertoken(self, ctx):
        """Generates and sends a token for use on VTTs."""

        char: Character = await Character.from_ctx(ctx)
        color_override = char.get_setting('color')
        if not char.image:
            return await ctx.send("This character has no image.")

        try:
            processed = await generate_token(char.image, color_override)
        except Exception as e:
            return await ctx.send(f"Error generating token: {e}")

        file = discord.File(processed, filename="image.png")
        embed = EmbedWithCharacter(char, image=False)
        embed.set_image(url="attachment://image.png")
        await ctx.send(file=file, embed=embed)

    @commands.command()
    async def sheet(self, ctx):
        """Prints the embed sheet of your currently active character."""
        char: Character = await Character.from_ctx(ctx)

        await ctx.send(embed=char.get_sheet_embed())
        await try_delete(ctx.message)

    @commands.group(aliases=['char'], invoke_without_command=True)
    async def character(self, ctx, *, name: str = None):
        """Switches the active character."""
        user_characters = await self.bot.mdb.characters.find({"owner": str(ctx.author.id)}).to_list(None)
        if not user_characters:
            return await ctx.send('You have no characters.')

        if name is None:
            active_character: Character = await Character.from_ctx(ctx)
            return await ctx.send(f'Currently active: {active_character.name}')

        selected_char = await search_and_select(ctx, user_characters, name, lambda e: e['name'],
                                                selectkey=lambda e: f"{e['name']} (`{e['upstream']}`)")

        char = Character.from_dict(selected_char)
        await char.set_active(ctx)

        await try_delete(ctx.message)

        await ctx.send(f"Active character changed to {char.name}.", delete_after=20)

    @character.command(name='list')
    async def character_list(self, ctx):
        """Lists your characters."""
        user_characters = await self.bot.mdb.characters.find(
            {"owner": str(ctx.author.id)}, ['name']
        ).to_list(None)
        if not user_characters:
            return await ctx.send('You have no characters.')
        await ctx.send('Your characters:\n{}'.format(', '.join(c['name'] for c in user_characters)))

    @character.command(name='delete')
    async def character_delete(self, ctx, *, name):
        """Deletes a character."""
        user_characters = await self.bot.mdb.characters.find(
            {"owner": str(ctx.author.id)}, ['name', 'upstream']
        ).to_list(None)
        if not user_characters:
            return await ctx.send('You have no characters.')

        selected_char = await search_and_select(ctx, user_characters, name, lambda e: e['name'],
                                                selectkey=lambda e: f"{e['name']} (`{e['upstream']}`)")

        await ctx.send(f"Are you sure you want to delete {selected_char['name']}? (Reply with yes/no)")
        try:
            reply = await self.bot.wait_for('message', timeout=30, check=auth_and_chan(ctx))
        except asyncio.TimeoutError:
            reply = None
        reply = get_positivity(reply.content) if reply is not None else None
        if reply is None:
            return await ctx.send('Timed out waiting for a response or invalid response.')
        elif reply:
            await Character.delete(ctx, str(ctx.author.id), selected_char['upstream'])
            return await ctx.send(f"{selected_char['name']} has been deleted.")
        else:
            return await ctx.send("OK, cancelling.")

    @commands.command()
    @commands.cooldown(1, 15, BucketType.user)
    async def update(self, ctx, *args):
        """Updates the current character sheet, preserving all settings.
        __Valid Arguments__
        `-v` - Shows character sheet after update is complete.
        `-cc` - Updates custom counters from Dicecloud."""
        old_character: Character = await Character.from_ctx(ctx)
        url = old_character.upstream
        args = argparse(args)

        prefixes = 'dicecloud-', 'google-', 'beyond-'
        _id = url[:]
        for p in prefixes:
            if url.startswith(p):
                _id = url[len(p):]
                break
        sheet_type = old_character.sheet_type
        if sheet_type == 'dicecloud':
            parser = DicecloudParser(_id)
            loading = await ctx.send('Updating character data from Dicecloud...')
        elif sheet_type == 'google':
            parser = GoogleSheet(_id)
            loading = await ctx.send('Updating character data from Google...')
        elif sheet_type == 'beyond':
            parser = BeyondSheetParser(_id)
            loading = await ctx.send('Updating character data from Beyond...')
        else:
            return await ctx.send(f"Error: Unknown sheet type {sheet_type}.")

        try:
            character = await parser.load_character(str(ctx.author.id), args)
        except ExternalImportError as eep:
            return await loading.edit(content=f"Error loading character: {eep}")
        except Exception as eep:
            log.warning(f"Error importing character {old_character.upstream}")
            log.warning(traceback.format_exc())
            return await loading.edit(content=f"Error loading character: {eep}")

        character.update(old_character)

        await character.commit(ctx)
        await character.set_active(ctx)
        await loading.edit(content=f"Updated and saved data for {character.name}!")
        if args.last('v'):
            await ctx.send(embed=character.get_sheet_embed())

    @commands.command()
    async def transferchar(self, ctx, user: discord.Member):
        """Gives a copy of the active character to another user."""
        character: Character = await Character.from_ctx(ctx)
        overwrite = ''

        conflict = await self.bot.mdb.characters.find_one({"owner": str(user.id), "upstream": character.upstream})
        if conflict:
            overwrite = "**WARNING**: This will overwrite an existing character."

        await ctx.send(f"{user.mention}, accept a copy of {character.name}? (Type yes/no)\n{overwrite}")
        try:
            m = await self.bot.wait_for('message', timeout=300,
                                        check=lambda msg: msg.author == user
                                                          and msg.channel == ctx.channel
                                                          and get_positivity(msg.content) is not None)
        except asyncio.TimeoutError:
            m = None

        if m is None or not get_positivity(m.content): return await ctx.send("Transfer not confirmed, aborting.")

        character.owner = str(user.id)
        await character.commit(ctx)
        await ctx.send(f"Copied {character.name} to {user.display_name}'s storage.")

    @commands.command()
    async def csettings(self, ctx, *args):
        """Updates personalization settings for the currently active character.
        Valid Arguments:
        `color <hex color>` - Colors all embeds this color.
        `criton <number>` - Makes attacks crit on something other than a 20.
        `reroll <number>` - Defines a number that a check will automatically reroll on, for cases such as Halfling Luck.
        `srslots true/false` - Enables/disables whether spell slots reset on a Short Rest.
        `embedimage true/false` - Enables/disables whether a character's image is automatically embedded.
        `critdice <number>` - Adds additional dice for to critical attacks.
        `talent true/false` - Enables/disables whether to apply a rogue's Reliable Talent on checks you're proficient with."""
        char = await Character.from_ctx(ctx)

        out = ['Operations complete!']
        skip = False
        for i, arg in enumerate(args):
            if skip:
                continue
            if arg in CHARACTER_SETTINGS:
                skip = True
                out.append(CHARACTER_SETTINGS[arg].run(ctx, char, list_get(i + 1, None, args)))

        await char.commit(ctx)
        await ctx.send('\n'.join(out))

    @commands.group(invoke_without_command=True)
    async def cvar(self, ctx, name: str = None, *, value=None):
        """Commands to manage character variables for use in snippets and aliases.
        See the [aliasing guide](https://avrae.io/cheatsheets/aliasing) for more help."""
        if name is None:
            return await ctx.invoke(self.bot.get_command("cvar list"))

        character: Character = await Character.from_ctx(ctx)

        if value is None:  # display value
            cvar = character.get_scope_locals().get(name)
            if cvar is None:
                return await ctx.send("This cvar is not defined.")
            return await ctx.send(f'**{name}**: ```\n{cvar}\n```')

        if not name.isidentifier():
            return await ctx.send("Cvar names must be identifiers "
                                  "(only contain a-z, A-Z, 0-9, _, and not start with a number).")
        if name in character.get_scope_locals(True):
            return await ctx.send("This variable is already built in!")

        character.set_cvar(name, value)
        await character.commit(ctx)
        await ctx.send('Character variable `{}` set to: `{}`'.format(name, value))

    @cvar.command(name='remove', aliases=['delete'])
    async def remove_cvar(self, ctx, name):
        """Deletes a cvar from the currently active character."""
        char: Character = await Character.from_ctx(ctx)
        if name not in char.cvars:
            return await ctx.send('Character variable not found.')

        del char.cvars[name]

        await char.commit(ctx)
        await ctx.send('Character variable {} removed.'.format(name))

    @cvar.command(name='deleteall', aliases=['removeall'])
    async def cvar_deleteall(self, ctx):
        """Deletes ALL character variables for the active character."""
        char: Character = await Character.from_ctx(ctx)

        await ctx.send(f"This will delete **ALL** of your character variables for {char.name}. "
                       "Are you *absolutely sure* you want to continue?\n"
                       "Type `Yes, I am sure` to confirm.")
        try:
            reply = await self.bot.wait_for('message', timeout=30, check=auth_and_chan(ctx))
        except asyncio.TimeoutError:
            reply = None
        if (not reply) or (not reply.content == "Yes, I am sure"):
            return await ctx.send("Unconfirmed. Aborting.")

        char.cvars = {}

        await char.commit(ctx)
        return await ctx.send(f"OK. I have deleted all of {char.name}'s cvars.")

    @cvar.command(name='list')
    async def list_cvar(self, ctx):
        """Lists all cvars for the currently active character."""
        character: Character = await Character.from_ctx(ctx)
        await ctx.send('{}\'s character variables:\n{}'.format(character.name,
                                                               ', '.join(sorted(character.cvars.keys()))))

    async def _confirm_overwrite(self, ctx, _id):
        """Prompts the user if command would overwrite another character.
        Returns True to overwrite, False or None otherwise."""
        conflict = await self.bot.mdb.characters.find_one({"owner": str(ctx.author.id), "upstream": _id})
        if conflict:
            await ctx.channel.send(
                "Warning: This will overwrite a character with the same ID. Do you wish to continue (reply yes/no)?\n"
                f"If you only wanted to update your character, run `{ctx.prefix}update` instead.")
            try:
                reply = await self.bot.wait_for('message', timeout=30, check=auth_and_chan(ctx))
            except asyncio.TimeoutError:
                reply = None
            replyBool = get_positivity(reply.content) if reply is not None else None
            return replyBool
        return True

    @commands.command()
    async def dicecloud(self, ctx, url: str, *args):
        """Loads a character sheet from [Dicecloud](https://dicecloud.com/), resetting all settings.
        Share your character with `avrae` on Dicecloud (edit perms) for live updates.
        __Valid Arguments__
        `-cc` - Will automatically create custom counters for class resources and features."""
        if 'dicecloud.com' in url:
            url = url.split('/character/')[-1].split('/')[0]

        override = await self._confirm_overwrite(ctx, f"dicecloud-{url}")
        if not override: return await ctx.send("Character overwrite unconfirmed. Aborting.")

        loading = await ctx.send('Loading character data from Dicecloud...')
        parser = DicecloudParser(url)
        await self._load_sheet(ctx, parser, args, loading)

    @commands.command()
    async def gsheet(self, ctx, url: str, *args):
        """Loads a character sheet from [GSheet v2.0](http://gsheet2.avrae.io) (auto) or [GSheet v1.4](http://gsheet.avrae.io) (manual), resetting all settings.
        The sheet must be shared with Avrae for this to work.
        Avrae's google account is `avrae-320@avrae-bot.iam.gserviceaccount.com`."""

        loading = await ctx.send('Loading character data from Google... (This usually takes ~30 sec)')
        try:
            url = extract_gsheet_id_from_url(url)
        except ExternalImportError:
            return await loading.edit(content="This is not a Google Sheets link.")

        override = await self._confirm_overwrite(ctx, f"google-{url}")
        if not override: return await ctx.send("Character overwrite unconfirmed. Aborting.")

        parser = GoogleSheet(url)
        await self._load_sheet(ctx, parser, args, loading)

    @commands.command()
    async def beyond(self, ctx, url: str, *args):
        """Loads a character sheet from [D&D Beyond](https://www.dndbeyond.com/), resetting all settings."""

        loading = await ctx.send('Loading character data from Beyond...')
        url = re.search(r"/characters/(\d+)", url)
        if url is None:
            return await loading.edit(content="This is not a D&D Beyond link.")
        url = url.group(1)

        override = await self._confirm_overwrite(ctx, f"beyond-{url}")
        if not override: return await ctx.send("Character overwrite unconfirmed. Aborting.")

        parser = BeyondSheetParser(url)
        await self._load_sheet(ctx, parser, args, loading)

    @staticmethod
    async def _load_sheet(ctx, parser, args, loading):
        try:
            character = await parser.load_character(str(ctx.author.id), argparse(args))
        except ExternalImportError as eep:
            return await loading.edit(content=f"Error loading character: {eep}")
        except Exception as eep:
            log.warning(f"Error importing character {parser.url}")
            log.warning(traceback.format_exc())
            return await loading.edit(content=f"Error loading character: {eep}")

        await loading.edit(content=f'Loaded and saved data for {character.name}!')

        await character.commit(ctx)
        await character.set_active(ctx)
        await ctx.send(embed=character.get_sheet_embed())


def setup(bot):
    bot.add_cog(SheetManager(bot))
