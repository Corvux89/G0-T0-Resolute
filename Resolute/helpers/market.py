import re
import discord
from Resolute.bot import G0T0Bot
from Resolute.helpers.characters import get_character
from Resolute.helpers.logs import get_log
from Resolute.helpers.players import get_player
from Resolute.models.categories.categories import TransactionSubType, TransactionType
from Resolute.models.objects.logs import DBLog
from Resolute.models.objects.market import MarketTransaction


async def get_market_request(bot: G0T0Bot, message: discord.Message) -> MarketTransaction:
    embed = message.embeds[0]
    
    player_id = get_match(r"\*\*Player\*\*:\s*<@(\d+)>\n", embed.description)
    char_id = get_match(r"\*\*Character\*\*:.*\[(\d+)\]", embed.description)
    type = get_match(f"(?<=\*\*Type\*\*:)\s(.*?)(?=\n)", embed.description)

    if player_id is None or char_id is None or type is None:
        return None

    subtype = get_match(r"\(([^)]+)\)", type)
    if subtype:
        type = type.replace(f' ({subtype})','')

    cc = get_match(r"\*\*Total\sCC\*\*:\s*([\d,]+)", embed.description,1,"0")
    credits = get_match(r"\*\*Total\sCredits\*\*:\s*([\d,]+)", embed.description,1,"0")


    if len(embed.fields) > 0:
        notes = "".join(x.value for x in embed.fields)
    else:
        notes = None

    player = await get_player(bot, int(player_id), message.guild.id)

    if char_id:
        character = await get_character(bot, char_id)
    else:
        character = None
    
    transaction = MarketTransaction(player,
                                    type=bot.compendium.get_object(TransactionType, type),
                                    subtype=bot.compendium.get_object(TransactionSubType, subtype),
                                    notes=notes,
                                    cc=int(cc.replace(',', '')),
                                    credits=int(credits.replace(',','')),
                                    character=character,
                                    message=message)


    return transaction

def get_match(pattern, text, group=1, default=None):
    match = re.search(pattern, text, re.DOTALL)
    return match.group(group) if match and match.group(group) != 'None' else default
    
