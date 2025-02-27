class Powerbook:
    def __init__(
        self,
        tech_points: int = 0,
        max_tech_points: int = 0,
        force_points: int = 0,
        max_force_points: int = 0,
        powers: list = None,
        dc=None,
        sab=None,
        caster_level=0,
        power_mod=None,
    ):
        self.tech_points = tech_points
        self.max_tech_points = max_tech_points
        self.force_points = force_points
        self.max_force_points = max_force_points
        self.powers = powers if powers else []
        self.dc = dc
        self.sab = sab
        self.caster_level = caster_level
        self.power_mod = power_mod

    @classmethod
    def from_dict(cls, d):
        d["powers"] = [PowerbookPower.from_dict(s) for s in d["powers"]]
        return cls(**d)

    def to_dict(self):
        return {
            "slots": self.slots,
            "max_slots": self.max_slots,
            "spells": [s.to_dict() for s in self.spells],
            "dc": self.dc,
            "sab": self.sab,
            "caster_level": self.caster_level,
            "spell_mod": self.spell_mod,
            "pact_slot_level": self.pact_slot_level,
            "num_pact_slots": self.num_pact_slots,
            "max_pact_slots": self.max_pact_slots,
        }


class PowerbookPower:
    def __init__(
        self,
        name,
        strict=False,
        level: int = None,
        dc: int = None,
        sab: int = None,
        mod: int = None,
    ):
        self.name = name
        self.strict = strict
        self.level = level
        self.dc = dc
        self.sab = sab
        self.mod = mod  # spellcasting ability mod

    @classmethod
    def from_spell(cls, power, dc=None, sab=None, mod=None):
        strict = power.source != "homebrew"
        return cls(power.name, strict, power.level, dc, sab, mod)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def to_dict(self):
        d = {"name": self.name, "strict": self.strict}
        for optional_key in ("level", "dc", "sab", "mod"):
            # minor storage optimization: don't store unncessary attributes
            v = getattr(self, optional_key)
            if v is not None:
                d[optional_key] = v
        return d
