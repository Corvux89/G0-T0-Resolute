from discord.ext import commands
import logging

from quart import jsonify, request, abort

from Resolute.bot import G0T0Bot
from Resolute.constants import AUTH_TOKEN, ERROR_CHANNEL



log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(WebCog(bot))

class WebCog(commands.Cog):
    bot: G0T0Bot

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        self.auth(bot)
        self.routes(bot)
        log.info(f'Cog \'Web\' loaded')

    @staticmethod
    def auth(bot: G0T0Bot):
        @bot.web_app.before_request
        async def verify_token():
            auth_token = request.headers.get('auth-token')

            if not auth_token or auth_token != AUTH_TOKEN:
                return jsonify({"error": "You don't have access to this"}), 401
    
    @staticmethod
    def routes(bot: G0T0Bot):
        # Reload the compendium
        @bot.web_app.route('/reload', methods=['POST'])
        async def reload(self):
            try:
                data = await request.json
            except:
                return abort(401)
            
            await bot.compendium.reload_categories(self.bot)
            await bot.get_channel(int(ERROR_CHANNEL)).send(data['text'])
            return jsonify({'text': 'Compendium Reloaded!'}), 200
        
        @bot.web_app.route('/guild_update', methods=['POST'])
        async def reload_guild(self):
            try:
                data = await request.json
            except:
                return abort(401)
            guild = await bot.get_player_guild(int(data['guild_id']))
            bot.dispatch("refresh_guild_cache", guild)
            await bot.get_channel(int(ERROR_CHANNEL)).send(data['text'])
            return jsonify({'text': 'Guild Cache Reloaded!'}), 200

    
