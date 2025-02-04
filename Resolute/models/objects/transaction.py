

from discord import Member
from Resolute.bot import G0T0Bot
from Resolute.models.categories.categories import Activity, Faction
from Resolute.models.embeds.logs import LogEmbed
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.characters import PlayerCharacter, upsert_character_query
from Resolute.models.objects.exceptions import TransactionError
from Resolute.models.objects.logs import DBLog, LogSchema, upsert_log
from Resolute.models.objects.players import Player, upsert_player_query


class Transaction(object):
    async def __init__(self, bot: G0T0Bot, player: Member|Player, author: Member|Player, activity: Activity|str, **kwargs):
        self._bot: G0T0Bot = bot
        self.player: Player = player if isinstance(player, Player) else await self._bot.get_player(player.id, player.guild.id)
        self.author: Player = author if isinstance(author, Player) else await self._bot.get_player(author.id, author.guild.id)
        self.activity = activity if isinstance(activity, Activity) else self._bot.compendium.get_activity(activity)

        self._cc = kwargs.get('cc')
        self.credits = kwargs.get('credits', 0)
        self.notes = kwargs.get('notes')
        self.character: PlayerCharacter = kwargs.get('character')
        self._ignore_handicap = kwargs.get('ignore_handicap', False)        

        self.renown = kwargs.get('renown', 0)
        self.faction: Faction = kwargs.get('faction')

        self.adventure: Adventure = kwargs.get('adventure')

    @property
    def reward_cc(self) -> int:
        reward_cc = self._cc if self._cc else self.activity.cc if self.activity.cc else 0

        if self.activity.diversion and (self.player.div_cc + reward_cc > self.player.guild.div_limit):
            reward_cc = 0 if self.player.guild.div_limit - self.player.div_cc < 0 else self.player.guild.div_limit - self.player.div_cc

        return reward_cc

    @property
    def cc(self) -> int:
        return self.reward_cc + self.handicap_amount
        
    @cc.setter
    def cc(self, value):
        self._cc = value

    @property
    def handicap_amount(self) -> int:
        if self._ignore_handicap or self.player.guild.handicap_cc <= self.player.handicap_amount:
            return 0
        
        return min(self.reward_cc, self.player.guild.handicap_cc - self.player.handicap_amount)
    

    async def commit(self) -> DBLog:
        log_entry = DBLog(author=self.author.id,
                          cc=self.cc,
                          credits=self.credits,
                          player_id=self.player.id,
                          character_id=self.character.id if self.character else None,
                          activity=self.activity,
                          notes=self.notes,
                          guild_id=self.player.guild_id,
                          adventure_id=self.adventure.id if self.adventure else None,
                          faction=self.faction,
                          renown=self.renown)
        
        if self.character and self.character.credits + log_entry.credits < 0:
            raise TransactionError(f"{self.character.name} cannot afford the {log_entry.credits} credit cost.")
        elif self.player.cc + log_entry.cc < 0:
            raise TransactionError(f"{self.player.member.mention} cannot afford the {log_entry.cc} CC cost.")
        

        if self.character:
            self.character.credits += log_entry.credits

        self.player.cc += log_entry.cc
        self.player.handicap_amount += self.handicap_amount

        if self.activity.diversion:
            self.player.div_cc += self.reward_cc

        if self.faction:
            await self.character.update_renown(self.faction, self.renown)


        async with self._bot.db.acquire() as conn:
            results = await conn.execute(upsert_log(log_entry))
            row = await results.first()

            await conn.execute(upsert_player_query(self.player))

            if self.character:
                await conn.execute(upsert_character_query(self.character))
        
        log_entry = LogSchema(self._bot.compendium).load(row)

        # Author Rewards
        if self.author.guild.reward_threshold and self.activity.value != "LOG_REWARD":
            self.author.points += self.activity.points

            if self.author.points >= self.author.guild.reward_threshold:
                qty = max(1, self.author.points//self.author.guild.reward_threshold)
                act = self._bot.compendium.get_activity("LOG_REWARD")
                reward_log = await Transaction(self._bot, self.author, self._bot.user,
                                         cc=act.cc*qty,
                                         notes=f"Rewards for {self.author.guild.reward_threshold*qty} points").commit()
                
                self.author.points = max(0, self.author.points - (self.author.guild.reward_threshold * qty))

                if self.author.guild.staff_channel:
                    await self.author.guild.staff_channel.send(embed=LogEmbed(reward_log, self._bot.user, self.author, None, True))

                async with self._bot.db.acquire() as conn:
                    await conn.execute(upsert_character_query(self.author))

        return log_entry


        

            


        

    