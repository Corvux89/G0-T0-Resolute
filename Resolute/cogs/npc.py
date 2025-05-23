import logging
from discord.ext import commands
from timeit import default_timer as timer

from Resolute.bot import G0T0Bot
from Resolute.models.objects.adventures import Adventure
from Resolute.models.objects.enum import WebhookType
from Resolute.models.objects.exceptions import AdventureNotFound, G0T0CommandError
from Resolute.models.objects.npc import NonPlayableCharacter
from Resolute.models.objects.webhook import G0T0Webhook

log = logging.getLogger(__name__)


def setup(bot: G0T0Bot):
    bot.add_cog(NPC(bot))


class NPC(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot):
        self.bot = bot
        log.info(f"Cog 'NPC' loaded")

    @commands.Cog.listener()
    async def on_db_connected(self):
        start = timer()
        npcs = await NonPlayableCharacter.get_all(self.bot)

        for npc in npcs:
            await npc.register_command(self.bot)
        end = timer()
        log.info(f"NPC: NPC's loaded in [ {end-start:.2f} ]s")

    def create_npc_command(self, npc: NonPlayableCharacter):
        async def npc_command(ctx):
            if ctx.invoked_with == "say":
                return

            adventure = None
            if npc.adventure_id:
                try:
                    adventure = Adventure.fetch_from_ctx(
                        ctx, adventure_id=npc.adventure_id
                    )
                except AdventureNotFound:
                    raise G0T0CommandError(
                        "This npc can only be used in it's designated Adventure"
                    )

            type = WebhookType.adventure if npc.adventure_id else WebhookType.npc
            await G0T0Webhook(ctx, type=type, adventure=adventure).send()

        return npc_command
