from enum import Enum


class ApplicationType(Enum):
    """
    Enum representing different types of applications.
    Attributes:
        new (str): Represents a new character application.
        death (str): Represents a death reroll application.
        freeroll (str): Represents a free reroll application.
        level (str): Represents a level up application.
    """

    new = "New Character"
    death = "Death Reroll"
    freeroll = "Free Reroll"
    level = "Level Up"


class ArenaPostType(Enum):
    """
    Enum class representing the types of posts that can be made in an arena.
    Attributes:
        COMBAT (str): Represents a combat post type.
        NARRATIVE (str): Represents a narrative post type.
        BOTH (str): Represents a post type that can be either combat or narrative.
    """

    COMBAT = "Combat"
    NARRATIVE = "Narrative"
    BOTH = "Combat or Narrative"


class AdjustOperator(Enum):
    """
    Enum class representing adjustment operators.
    Attributes:
        less (str): Represents the less than or equal to operator ("<=").
        greater (str): Represents the greater than or equal to operator (">=").
    """

    less = "<="
    greater = ">="


class WebhookType(Enum):
    """
    Enum representing different types of webhooks.
    Attributes:
        npc (str): Represents a non-player character webhook.
        adventure (str): Represents an adventure webhook.
        say (str): Represents a say webhook.
    """

    npc = "npc"
    adventure = "adventure"
    say = "say"
