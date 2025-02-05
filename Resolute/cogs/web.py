import logging

from discord.ext import commands
from quart import abort, jsonify, request

from Resolute.bot import G0T0Bot
from Resolute.constants import AUTH_TOKEN, ERROR_CHANNEL

log = logging.getLogger(__name__)

def setup(bot: commands.Bot):
    bot.add_cog(WebCog(bot))

class WebCog(commands.Cog):
    """
    WebCog is a Discord bot cog that provides web routes and authentication for the bot's web application.
    Attributes:
        bot (G0T0Bot): The instance of the bot.
    Methods:
        __init__(bot: G0T0Bot):
            Initializes the WebCog with the given bot instance, sets up authentication and routes, and logs the loading of the cog.
        auth(bot: G0T0Bot):
            Static method that sets up a before_request hook to verify the authentication token in incoming requests.
        routes(bot: G0T0Bot):
            Static method that sets up web routes for the bot's web application.
            Routes:
                /reload (POST):
                    Reloads the compendium categories and sends a message to the error channel.
                /guild_update (POST):
                    Reloads the guild cache and sends a message to the error channel.
    """
    bot: G0T0Bot

    def __init__(self, bot: G0T0Bot):
        self.bot = bot
        self.auth(bot)
        self.routes(bot)
        log.info(f'Cog \'Web\' loaded')

    @staticmethod
    def auth(bot: G0T0Bot):
        """
        Registers a before_request hook on the bot's web application to verify the presence and validity of an authentication token.
        Args:
            bot (G0T0Bot): The bot instance to which the web application belongs.
        Returns:
            None
        Raises:
            401 Unauthorized: If the 'auth-token' header is missing or invalid, a JSON response with an error message is returned.
        """
        @bot.web_app.before_request
        async def verify_token():
            auth_token = request.headers.get('auth-token')

            if not auth_token or auth_token != AUTH_TOKEN:
                return jsonify({"error": "You don't have access to this"}), 401
    
    @staticmethod
    def routes(bot: G0T0Bot):
        """
        Defines the routes for the web application.
        Routes:
            /reload (POST): Reloads the compendium categories and sends a notification to the error channel.
            /guild_update (POST): Reloads the guild cache and sends a notification to the error channel.
        Args:
            bot (G0T0Bot): The bot instance to which the routes are added.
        Functions:
            reload(self): Handles the /reload route. Reloads the compendium categories and sends a notification.
            reload_guild(self): Handles the /guild_update route. Reloads the guild cache and sends a notification.
        """
        # Reload the compendium
        @bot.web_app.route('/reload', methods=['POST'])
        async def reload():
            try:
                data = await request.json
            except:
                return abort(401)
            
            await bot.compendium.reload_categories(bot)
            await bot.get_channel(int(ERROR_CHANNEL)).send(data['text'])
            return jsonify({'text': 'Compendium Reloaded!'}), 200
        
        @bot.web_app.route('/guild_update', methods=['POST'])
        async def reload_guild():
            try:
                data = await request.json
            except:
                return abort(401)
            guild = await bot.get_player_guild(int(data['guild_id']))
            bot.dispatch("refresh_guild_cache", guild)
            await bot.get_channel(int(ERROR_CHANNEL)).send(data['text'])
            return jsonify({'text': 'Guild Cache Reloaded!'}), 200

    
