from __future__ import annotations
from typing import TYPE_CHECKING

import re

import discord
import sqlalchemy as sa
from marshmallow import Schema, fields
from Resolute.models import metadata
from Resolute.models.objects.enum import ApplicationType, QueryResultType
from Resolute.models.objects.exceptions import G0T0Error

if TYPE_CHECKING:
    from Resolute.models.objects.characters import PlayerCharacter
    from Resolute.bot import G0T0Bot


class AppBaseScores(object):
    """
    A class to represent base scores for an application.
    Attributes:
    ----------
    str : str
        Strength attribute (default is an empty string).
    dex : str
        Dexterity attribute (default is an empty string).
    con : str
        Constitution attribute (default is an empty string).
    int : str
        Intelligence attribute (default is an empty string).
    wis : str
        Wisdom attribute (default is an empty string).
    cha : str
        Charisma attribute (default is an empty string).
    Methods:
    -------
    status():
        Returns the status of the attributes.
    output():
        Returns a formatted string of the attributes.
    """

    def __init__(self, **kwargs):
        self.str = kwargs.get("str", "")
        self.dex = kwargs.get("dex", "")
        self.con = kwargs.get("con", "")
        self.int = kwargs.get("int", "")
        self.wis = kwargs.get("wis", "")
        self.cha = kwargs.get("cha", "")

    @property
    def status(self) -> str:
        """
        Returns the status of the object based on its attributes.
        This method collects the object's attributes (strength, dexterity,
        constitution, intelligence, wisdom, and charisma) into a list and
        returns their status.
        Returns:
            status: The status of the object based on its attributes.
        """
        attributes = [self.str, self.dex, self.con, self.int, self.wis, self.cha]

        return status(attributes)

    def output(self) -> str:
        """
        Generates a formatted string representing the character's attributes.
        Returns:
            str: A string containing the character's attributes (STR, DEX, CON, INT, WIS, CHA)
                 formatted with their respective values.
        """
        return (
            f"**STR:** {self.str}\n"
            f"**DEX:** {self.dex}\n"
            f"**CON:** {self.con}\n"
            f"**INT:** {self.int}\n"
            f"**WIS:** {self.wis}\n"
            f"**CHA:** {self.cha}\n"
        )


class AppSpecies(object):
    """
    A class to represent a species in an application.
    Attributes
    ----------
    species : str
        The name of the species.
    asi : str
        The ability score improvements (ASIs) of the species.
    feats : str
        The features of the species.
    Methods
    -------
    get_field():
        Returns a formatted string with the species, ASIs, and features.
    status():
        Returns the status of the species attributes.
    output():
        Returns a formatted string with the species, ASIs, and features.
    """

    def __init__(self, **kwargs):
        self.species = kwargs.get("species", "")
        self.asi = kwargs.get("asi", "")
        self.feats = kwargs.get("feats", "")

    def get_field(self) -> str:
        """
        Retrieves the field information for the object.
        Returns:
            str: A formatted string containing the species, ASIs, and features of the object if the species attribute is set.
                 Otherwise, returns "Not set".
        """
        if not hasattr(self, "species"):
            return "Not set"
        else:
            return f"**{self.species}**\nASIs: {self.asi}\nFeatures: {self.feats}"

    @property
    def status(self) -> str:
        """
        Retrieve the status of the application.
        This method collects the attributes of the application, which include
        species, asi, and feats, and returns their status.
        Returns:
            status: The status of the application's attributes.
        """
        attributes = [self.species, self.asi, self.feats]

        return status(attributes)

    def output(self) -> str:
        """
        Generates a formatted string containing the species, ASI, and features of the object.
        Returns:
            str: A formatted string with the species, ASI, and features.
        """
        return (
            f"**Species:** {self.species}\n"
            f"**ASI:** {self.asi}\n"
            f"**Features:** {self.feats}\n"
        )


class AppClass(object):
    """
    A class to represent an application with various attributes.
    Attributes:
    -----------
    char_class : str
        The character class of the application.
    skills : str
        The skills associated with the application.
    feats : str
        The feats associated with the application.
    equipment : str
        The equipment associated with the application.
    Methods:
    --------
    __init__(**kwargs):
        Initializes the AppClass with given attributes.
    status():
        Returns the status of the application.
    output():
        Returns a formatted string representation of the application's attributes.
    """

    def __init__(self, **kwargs):
        self.char_class = kwargs.get("char_class", "")
        self.skills = kwargs.get("skills", "")
        self.feats = kwargs.get("feats", "")
        self.equipment = kwargs.get("equipment", "")

    @property
    def status(self) -> str:
        """
        Returns the status of the application by aggregating various attributes.
        This method collects the character class, skills, feats, and equipment
        of the application and returns their combined status.
        Returns:
            status: The combined status of the application's attributes.
        """
        attributes = [self.char_class, self.skills, self.feats, self.equipment]

        return status(attributes)

    def output(self) -> str:
        """
        Generates a formatted string containing the character's class, skills, features, and equipment.
        Returns:
            str: A formatted string with the character's class, skills, features, and equipment.
        """
        return (
            f"**Class:** {self.char_class}\n"
            f"**Skills:** {self.skills}\n"
            f"**Features:** {self.feats}\n"
            f"**Equipment:** {self.equipment}"
        )


class AppBackground(object):
    """
    A class to represent the background information of an application.
    Attributes:
    ----------
    background : str
        The background description.
    skills : str
        The skills associated with the background.
    tools : str
        The tools or languages associated with the background.
    feat : str
        The feat associated with the background.
    equipment : str
        The equipment associated with the background.
    Methods:
    -------
    __init__(**kwargs):
        Initializes the AppBackground with optional keyword arguments.
    status():
        Returns the status of the background attributes.
    output():
        Returns a formatted string representation of the background information.
    """

    background: str = ""
    skills: str = ""
    tools: str = ""
    feat: str = ""
    equipment: str = ""

    def __init__(self, **kwargs):
        self.background = kwargs.get("background", "")
        self.skills = kwargs.get("skills", "")
        self.tools = kwargs.get("tools", "")
        self.feat = kwargs.get("feat", "")
        self.equipment = kwargs.get("equipment", "")

    @property
    def status(self) -> str:
        """
        Returns the status of the application based on its attributes.
        This method collects various attributes of the application, such as
        background, skills, tools, feat, and equipment, and returns their
        combined status.
        Returns:
            status: The combined status of the application's attributes.
        """
        attributes = [
            self.background,
            self.skills,
            self.tools,
            self.feat,
            self.equipment,
        ]
        return status(attributes)

    def output(self) -> str:
        """
        Generates a formatted string containing the details of the application.
        Returns:
            str: A formatted string with the following details:
                - Background
                - Skills
                - Tools/Languages
                - Feat
                - Equipment
        """
        return (
            f"**Background:** {self.background}\n"
            f"**Skills:** {self.skills}\n"
            f"**Tools/Languages:** {self.tools}\n"
            f"**Feat:** {self.feat}\n"
            f"**Equipment:** {self.equipment}"
        )


class NewCharacterApplication(object):
    """
    A class to represent a new character application.
    Attributes:
    -----------
    message : Message
        The message associated with the application.
    character : PlayerCharacter
        The player character associated with the application.
    name : str
        The name of the character.
    type : ApplicationType
        The type of the application.
    base_scores : AppBaseScores
        The base scores of the character.
    species : AppSpecies
        The species of the character.
    char_class : AppClass
        The class of the character.
    background : AppBackground
        The background of the character.
    credits : str
        The credits of the character.
    homeworld : str
        The homeworld of the character.
    join_motivation : str
        The motivation for joining the Wardens of the Sky.
    good_motivation : str
        The motivation for doing good.
    link : str
        The link associated with the application.
    hp : str
        The hit points of the character.
    level : str
        The level of the character.
    Methods:
    --------
    can_submit():
        Checks if the application can be submitted.
    format_app(owner: Member, staff: Role = None):
        Formats the application for display.
    async load(bot, content: str = None, message: Message = None):
        Loads the application from the given content or message.
    """

    def __init__(self, **kwargs):
        self.message: discord.Message = kwargs.get("message")
        self.character: PlayerCharacter = kwargs.get("character")
        self.name = kwargs.get("name", "")
        self.type: ApplicationType = kwargs.get("type", ApplicationType.new)
        self.base_scores: AppBaseScores = kwargs.get("base_scores", AppBaseScores())
        self.species: AppSpecies = kwargs.get("species", AppSpecies())
        self.char_class: AppClass = kwargs.get("char_class", AppClass())
        self.background: AppBackground = kwargs.get("background", AppBackground())
        self.credits = kwargs.get("credits", "0")
        self.homeworld = kwargs.get("homeworld", "")
        self.join_motivation = kwargs.get("join_motivation", "")
        self.good_motivation = kwargs.get("good_motivation", "")
        self.link = kwargs.get("link", "")
        self.hp = kwargs.get("hp", "")
        self.level = kwargs.get("level", "1")

    def can_submit(self) -> bool:
        """
        Determines if the application can be submitted.
        This method checks if all required fields and statuses are complete and non-empty.
        The application can be submitted if:
        - The status of base_scores, species, char_class, and background are all 'Complete'.
        - The join_motivation, name, link, homeworld, and good_motivation fields are not empty.
        Returns:
            bool: True if the application can be submitted, False otherwise.
        """
        required_fields = [
            self.base_scores.status,
            self.species.status,
            self.char_class.status,
            self.background.status,
            self.join_motivation,
            self.name,
            self.link,
            self.homeworld,
            self.good_motivation,
        ]
        try:
            if all("Complete" in field or field for field in required_fields):
                return True
            else:
                return False
        except:
            return False

    def format_app(self, owner: discord.Member, staff: discord.Role = None) -> str:
        """
        Formats the application details into a string for display.
        Args:
            owner (Member): The owner of the application.
            staff (Role, optional): The staff member associated with the application. Defaults to None.
        Returns:
            str: A formatted string containing the application details.
        """
        hp_str = (
            f"**HP:** {self.hp}\n\n"
            if self.hp != "" and self.hp != "None" and self.hp is not None
            else ""
        )
        level_str = f"**Level:** {self.level}\n" if self.level != "" else ""
        reroll_str = (
            f"**Reroll From:** {self.character.name} [{self.character.id}]\n"
            if self.type in [ApplicationType.death, ApplicationType.freeroll]
            else ""
        )
        return (
            f"**{self.type.value}** | {staff.mention if staff else 'Archivist'}\n"
            f"{reroll_str}"
            f"**Name:** {self.name}\n"
            f"**Player:** {owner.mention}\n\n"
            f"**Base Scores:**\n"
            f"STR: {self.base_scores.str}\n"
            f"DEX: {self.base_scores.dex}\n"
            f"CON: {self.base_scores.con}\n"
            f"INT: {self.base_scores.int}\n"
            f"WIS: {self.base_scores.wis}\n"
            f"CHA: {self.base_scores.cha}\n\n"
            f"{level_str}"
            f"{hp_str}"
            f"**Species:** {self.species.species}\n"
            f"ASIs: {self.species.asi}\n"
            f"Features: {self.species.feats}\n\n"
            f"**Class:** {self.char_class.char_class}\n"
            f"Skills: {self.char_class.skills}\n"
            f"Features: {self.char_class.feats}\n\n"
            f"**Background:** {self.background.background}\n"
            f"Skills: {self.background.skills}\n"
            f"Tools/Languages: {self.background.tools}\n"
            f"Feat: {self.background.feat}\n\n"
            f"**Equipment:**\n"
            f"Class: {self.char_class.equipment}\n"
            f"Background: {self.background.equipment}\n"
            f"Credits: {self.credits}\n\n"
            f"**Homeworld:** {self.homeworld}\n"
            f"**Motivation for joining the Wardens of the Sky:** {self.join_motivation}\n\n"
            f"**Motivation for doing good:** {self.good_motivation}\n\n"
            f"**Link:** {self.link}"
        )

    async def load(
        self, bot, content: str = None, message: discord.Message = None
    ) -> "NewCharacterApplication":
        """
        Asynchronously loads a new character application from the provided content or message.
        Args:
            bot: The bot instance used to fetch character details if needed.
            content (str, optional): The content string to parse the application from. Defaults to None.
            message (Message, optional): The message object containing the application content. Defaults to None.
        Returns:
            NewCharacterApplication: The parsed character application object.
        """
        app_text = content or message.content

        def get_match(pattern, text, group=1, default=None):
            match = re.search(pattern, text, re.DOTALL)
            return (
                match.group(group)
                if match and match.group(group) != "None"
                else default
            )

        type_match = re.search(r"^\*\*(.*?)\*\*\s\|", app_text, re.MULTILINE)

        base_scores_match = re.search(
            r"STR: (.*?)\n"
            r"DEX: (.*?)\n"
            r"CON: (.*?)\n"
            r"INT: (.*?)\n"
            r"WIS: (.*?)\n"
            r"CHA: (.*?)\n",
            app_text,
        )

        species_match = re.search(
            r"\*\*Species:\*\* (.+?)\n" r"ASIs: (.+?)\n" r"Features: (.+?)\n",
            app_text,
            re.DOTALL,
        )

        char_class_match = re.search(
            r"\*\*Class:\*\* (.+?)\n"
            r"Skills: (.*?)(?=\nFeatures:)\n"
            r"Features: (.*?)(?=\n\n\*\*)",
            app_text,
            re.DOTALL,
        )

        background_match = re.search(
            r"\*\*Background:\*\* (.+?)\n"
            r"Skills: (.+?)\n"
            r"Tools/Languages: (.+?)\n"
            r"Feat: (.+?)\n\n",
            app_text,
        )

        equip_match = re.search(
            r"\*\*Equipment:\*\*\n"
            r"Class: (.*?)(?=\nBackground:)\n"
            r"Background: (.*?)(?=\nCredits:)",
            app_text,
            re.DOTALL,
        )

        char_id = get_match(r"\*\*Reroll\sFrom:\*\*(.*?)\s\[(\d+)\]\n", app_text, 2)

        application = NewCharacterApplication(
            message=message,
            name=get_match(r"\*\*Name:\*\* (.+?)\n\*\*Player", app_text),
            type=(
                next(
                    (
                        a
                        for a in ApplicationType
                        if a.value == type_match.group(1).strip().replace("*", "")
                    ),
                    ApplicationType.new,
                )
                if type_match
                else ApplicationType.new
            ),
            base_scores=AppBaseScores(
                str=base_scores_match.group(1) if base_scores_match else "",
                dex=base_scores_match.group(2) if base_scores_match else "",
                con=base_scores_match.group(3) if base_scores_match else "",
                int=base_scores_match.group(4) if base_scores_match else "",
                wis=base_scores_match.group(5) if base_scores_match else "",
                cha=base_scores_match.group(6) if base_scores_match else "",
            ),
            species=AppSpecies(
                species=species_match.group(1) if species_match else "",
                asi=species_match.group(2) if species_match else "",
                feats=species_match.group(3) if species_match else "",
            ),
            char_class=AppClass(
                char_class=char_class_match.group(1) if char_class_match else "",
                skills=char_class_match.group(2) if char_class_match else "",
                feats=char_class_match.group(3) if char_class_match else "",
                equipment=equip_match.group(1) if equip_match else "",
            ),
            background=AppBackground(
                background=background_match.group(1) if background_match else "",
                skills=background_match.group(2) if background_match else "",
                tools=background_match.group(3) if background_match else "",
                feat=background_match.group(4) if background_match else "",
                equipment=equip_match.group(2) if equip_match else "",
            ),
            credits=get_match(r"Credits: (.+?)\n", app_text, 1, "0"),
            homeworld=get_match(
                r"\*\*Homeworld:\*\* (.*?)(?=\n\*\*Motivation)", app_text
            ),
            join_motivation=get_match(
                r"\*\*Motivation for joining the Wardens of the Sky:\*\* (.*?)(?=\n\n\*\*)",
                app_text,
            ),
            good_motivation=get_match(
                r"\*\*Motivation for doing good:\*\* (.*?)(?=\n\n\*\*)", app_text
            ),
            link=get_match(r"\*\*Link:\*\* (.+)", app_text),
            level=get_match(r"\*\*Level:\*\* (.+?)\n", app_text),
            hp=get_match(r"\*\*HP:\*\* (.+?)\n", app_text),
        )

        if char_id:
            application.character = await bot.get_character(char_id)

        return application


def status(attributes=[]) -> str:
    """
    Determine the status of an application based on its attributes.
    Args:
        attributes (list): A list of attributes to check.
    Returns:
        str: A string representing the status of the application.
             - "<:x:983576786447245312> -- Incomplete" if all attributes are None or empty.
             - "<:white_check_mark:983576747381518396> -- Complete" if all attributes are non-empty.
             - "<:pencil:989284061786808380> -- In-Progress" if some attributes are empty and some are non-empty.
    """
    if all(a is None or a == "" for a in attributes):
        return "<:x:983576786447245312> -- Incomplete"
    elif all(a is not None and a != "" for a in attributes):
        return "<:white_check_mark:983576747381518396> -- Complete"
    else:
        return "<:pencil:989284061786808380> -- In-Progress"


class LevelUpApplication(object):
    """
    A class to represent a level-up application for a player character.
    Attributes
    ----------
    message : Message
        The message associated with the application.
    level : int
        The new level of the character.
    hp : int
        The new hit points of the character.
    feats : str
        The new features or feats of the character.
    changes : str
        Any changes made to the character.
    link : str
        A link associated with the application.
    character : PlayerCharacter
        The player character associated with the application.
    type : ApplicationType
        The type of application, set to 'level'.
    Methods
    -------
    format_app(owner: Member, staff: Role = None):
        Formats the application details into a string for display.
    async load(bot, content: str = None, message: Message = None):
        Loads the application details from a message or content string.
    """

    def __init__(self, **kwargs):
        self.message: discord.Message = kwargs.get("message")
        self.level = kwargs.get("level")
        self.hp = kwargs.get("hp")
        self.feats = kwargs.get("feats")
        self.changes = kwargs.get("changes")
        self.link = kwargs.get("link")
        self._character: PlayerCharacter = kwargs.get("character")
        self.type = ApplicationType.level

        if not self.level and self._character:
            self.level = self._character.level + 1

    @property
    def character(self):
        return self._character

    @character.setter
    def character(self, value):
        self._character = value

        if not self.level:
            self.level = self._character.level + 1

    def format_app(self, owner: discord.Member, staff: discord.Role = None) -> str:
        """
        Formats the application details for a character level-up.
        Args:
            owner (Member): The owner of the character.
            staff (Role, optional): The staff member handling the application. Defaults to None.
        Returns:
            str: A formatted string containing the level-up details.
        """
        return (
            f"**Level Up** | {staff.mention if staff else 'Archivist'}\n"
            f"**Name:** {self.character.name} [{self.character.id}]\n"
            f"**Player:** {owner.mention}\n\n"
            f"**New Level:** {self.level}\n"
            f"**HP:** {self.hp}\n"
            f"**New Features:** {self.feats}\n"
            f"**Changes:** {self.changes}\n"
            f"**Link:** {self.link}\n\n"
        )

    async def load(
        self, bot, content: str = None, message: discord.Message = None
    ) -> "LevelUpApplication":
        """
        Asynchronously loads an application from the provided content or message.
        Args:
            bot: The bot instance used to retrieve character information.
            content (str, optional): The content string to parse. Defaults to None.
            message (Message, optional): The message object containing the content to parse. Defaults to None.
        Returns:
            LevelUpApplication: An instance of LevelUpApplication with the parsed data.
        """
        app_text = content or message.content

        def get_match(pattern, text, group=1, default=None):
            match = re.search(pattern, text, re.DOTALL)
            return (
                match.group(group)
                if match and match.group(group) != "None"
                else default
            )

        char_id = get_match(r"\*\*Name:\*\*(.*?)\s\[(\d+)\]\n", app_text, 2)

        application = LevelUpApplication(
            message=message,
            level=get_match(r"\*\*New Level:\*\* (.+?)\n", app_text),
            hp=get_match(r"\*\*HP:\*\* (.+?)\n", app_text),
            feats=get_match(r"\*\*New Features:\*\* (.+?)(?=\n\*\*)", app_text),
            changes=get_match(r"\*\*Changes:\*\* (.+?)(?=\n\*\*)", app_text),
            link=get_match(r"\*\*Link:\*\* (.+)", app_text),
        )

        if char_id:
            application.character = await bot.get_character(char_id)

        return application


class PlayerApplication(object):
    """
    A class to represent a player's application in the game.
    Attributes:
    -----------
    cached : bool
        A flag indicating whether the application is cached.
    _bot : Bot
        The bot instance.
    owner : Member | User
        The owner of the application.
    application : NewCharacterApplication | LevelUpApplication
        The application instance.
    Methods:
    --------
    __init__(bot, owner, **kwargs):
        Initializes the PlayerApplication with the given bot and owner.
    async upsert():
        Inserts or updates the player's application in the database.
    async delete():
        Deletes the player's application from the database.
    async load(message: Message = None):
        Loads the player's application from the database or a given message.
    """

    cached: bool = False

    ref_applications_table = sa.Table(
        "ref_character_applications",
        metadata,
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("application", sa.String, nullable=False),
    )

    class ApplicationSchema(Schema):
        id = fields.Integer(required=True)
        application = fields.String(required=True)

    def __init__(self, bot: G0T0Bot, owner: discord.Member | discord.User, **kwargs):
        self._bot = bot
        self.owner = owner
        type: ApplicationType = kwargs.get("type", ApplicationType.new)
        self.edit: bool = kwargs.get("edit", False)

        if type in [
            ApplicationType.new,
            ApplicationType.death,
            ApplicationType.freeroll,
        ]:
            self.application = NewCharacterApplication(type=type)
        else:
            self.application = LevelUpApplication()

    async def insert(self) -> None:
        """
        Asynchronously inserts or updates the player's application in the database.
        If the application exists, it formats the application data for the owner and
        inserts or updates it in the database using an asynchronous connection.
        Returns:
            None
        """
        if self.application:
            query = PlayerApplication.ref_applications_table.insert().values(
                id=self.owner.id, application=self.application.format_app(self.owner)
            )
            await self._bot.query(query, QueryResultType.none)

    async def delete(self) -> None:
        """
        Asynchronously deletes the player application associated with the owner of this instance.
        This method acquires a database connection from the bot's connection pool and executes
        a deletion query to remove the player application for the owner.
        Returns:
            None
        """
        query = PlayerApplication.ref_applications_table.delete().where(
            PlayerApplication.ref_applications_table.c.id == self.owner.id
        )

        await self._bot.query(query, QueryResultType.none)

    async def load(self, message: discord.Message = None) -> "PlayerApplication":
        """
        Asynchronously loads the application data for the player.
        If a message is provided, it uses the content of the message to load the application.
        If no message is provided, it fetches the application data from the database.
        Args:
            message (Message, optional): The message containing the application data. Defaults to None.
        Returns:
            PlayerApplication: The loaded player application.
        Raises:
            G0T0Error: If the application type is unknown or if the application does not belong to the player.
        """
        if not message:
            query = PlayerApplication.ref_applications_table.select().where(
                PlayerApplication.ref_applications_table.c.id == self.owner.id
            )

            row = await self._bot.query(query)

            if row is None:
                return PlayerApplication(self._bot, self.owner)

            application = PlayerApplication.ApplicationSchema().load(row)
            self.cached = True
            content = application["application"]
        else:
            content = message.content

        player_match = re.search(r"^\*\*Player:\*\* (.+)", content, re.MULTILINE)
        type_match = re.search(r"^\*\*(.*?)\*\*\s\|", content, re.MULTILINE)
        type_string = (
            type_match.group(1).strip().replace("*", "") if type_match else None
        )
        type = ApplicationType(type_string) if type_string else None

        if player_match and str(self.owner.id) in player_match.group(1):
            if type and type in [
                ApplicationType.death,
                ApplicationType.freeroll,
                ApplicationType.new,
            ]:
                self.application = await NewCharacterApplication().load(
                    self._bot, content, message
                )
            elif type and type in [ApplicationType.level]:
                self.application = await LevelUpApplication().load(
                    self._bot, content, message
                )
            else:
                raise G0T0Error("Unsure what tye of application this is")
        else:
            raise G0T0Error("Not your application")
