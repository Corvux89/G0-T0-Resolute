from discord import Embed

from Resolute.models.objects.applications import (NewCharacterApplication,
                                                  status)


class NewCharacterRequestEmbed(Embed):
    def __init__(self, application: NewCharacterApplication):
        super().__init__(title=f"{application.type.value} Application")

        self.add_field(name="__Character Name__",
                       value=f"{status([application.name])}")
        
        self.add_field(name=f"__Base Scores__",
                       value=f"{application.base_scores.status()}")
        
        self.add_field(name=f"__Species__",
                       value=f"{application.species.status()}")
        
        self.add_field(name=f"__Class__",
                       value=f"{application.char_class.status()}")
        
        self.add_field(name="__Background__",
                       value=f"{application.background.status()}")
        
        self.add_field(name=f"__Joining Motivation__",
                       value=f"{status([application.join_motivation])}")

        self.add_field(name=f"__Motivation for Good__",
                       value=f"{status([application.good_motivation])}")
        
        self.add_field(name=f"__Starting Credits__",
                       value=f"{application.credits}")
        
        self.add_field(name=f"__Sheet Link__",
                       value=f"{application.link}")
        
        self.add_field(name="Instructions",
                       value="Fill out all the required fields, "
                             "or 'NA' if the specific section is not applicatble.\n"
                             "Review the appliation then submit when ready.",
                             inline=False)






        