import pytest

pytestmark = pytest.mark.asyncio


async def basic_commands(bot, dhttp):
    dhttp.clear()
    bot.message("!ping")
    await dhttp.receive_message("Pong.")
    await dhttp.receive_edit(r"Pong.\nHTTP Ping = \d+ ms.", regex=True)
