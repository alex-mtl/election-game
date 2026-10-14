"""Global settings (shared by all games): like balloons, the likes plane, voice, greetings.
Shown in the menu ("⚙ General settings"); defaults come from config, choices are fixed here.
The values are applied to the config module, which the rest of the code reads at use time."""

from . import config


class GlobalSettings:
    name = "global"
    # key -> (config attribute, choices); 1/0 = on/off
    OPTIONS = {
        "balloon_likes": ("LIKES_PER_BALLOON", [50, 100, 200, 500]),
        "plane_auto": ("PLANE_AUTO_LIKES", [0, 500, 1000, 2000, 5000]),
        "bomber": ("PLANE_BOMBER_LIKES", [0, 5000, 10000, 20000]),
        "voice_rate": ("VOICE_RATE", [1, 1.25, 1.5, 1.75, 2]),
        "greet": ("GREET_JOINS", [1, 0]),
    }

    def schema(self):
        return {k: choices for k, (_, choices) in self.OPTIONS.items()}

    def values(self):
        out = {}
        for k, (attr, _) in self.OPTIONS.items():
            v = getattr(config, attr)
            out[k] = int(v) if isinstance(v, bool) else v
        return out

    def set(self, key, value):
        if key not in self.OPTIONS:
            return False
        attr, choices = self.OPTIONS[key]
        if value not in choices:
            return False
        current = getattr(config, attr)
        setattr(config, attr, bool(value) if isinstance(current, bool) else type(current)(value))
        return True
