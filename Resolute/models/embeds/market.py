from discord import Color, Embed

from Resolute.models.objects.market import MarketTransaction


class TransactionEmbed(Embed):
    def __init__(self, transaction: MarketTransaction):
        super().__init__(title=f"Market Request - {transaction.character.name if transaction.character else transaction.player.member.display_name}",
                         color=Color.random())
        self.set_thumbnail(url=transaction.player.member.display_avatar.url)
        self.description=f"**Player**: {transaction.player.member.mention}\n"

        self.description += f"**Character**: {transaction.character.name} [{transaction.character.id}] \n" if transaction.character else ''

        self.description += f"**Type**: {transaction.format_type}\n"

        if transaction.cc > 0:
            self.description += f"**Total CC**: {transaction.cc:,}\n"

        if transaction.credits > 0:
            self.description += f"**Total Credits**: {transaction.credits:,}\n"

        chunk_size = 1000
        if transaction.notes:
            note_chunk = [transaction.notes[i:i+chunk_size] for i in range(0, len(transaction.notes), chunk_size)]

            for i, chunk in enumerate(note_chunk):
                self.add_field(name=f"Notes {f'{i+1}' if len(note_chunk) > 1 else ''}",
                            value=chunk,
                            inline=False)