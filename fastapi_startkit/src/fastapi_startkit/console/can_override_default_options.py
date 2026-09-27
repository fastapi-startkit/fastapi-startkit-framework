from cleo.commands.command import Command
from inflection import underscore


class CanOverrideOptionsDefault(Command):
    """Command mixin to allow to override optional argument default values when instantiating the
    command.
    Example: SomeCommand(app, option1="other/default").

    If an argument long name is using - then use _ in keyword argument:
    Example: SomeCommand(app, option_1="other/default") for an option named in option-1
    """

    def __init__(self, **kwargs):
        super().__init__()
        self.overriden_default = kwargs
        for option in self.definition.options:
            if hasattr(self, f"_{option.name}_default"):
                option.set_default(getattr(self, f"_{option.name}_default"))
            # Cleo does not authorize _ in option name but - are authorized and unfortunately -
            # cannot be used in Python variables. So underscore() is called to make sure that
            # an option like 'option-a' will be accessible with 'option_a' in kwargs
            default = self.overriden_default.get(underscore(option.name))
            if default:
                option.set_default(default)
