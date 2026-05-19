class SupportMixin:
    def __init__(self):
        pass

    @staticmethod
    def _extract_operator_value(*args):
        operators = [
            "=",
            ">",
            ">=",
            "<",
            "<=",
            "!=",
            "<>",
            "like",
            "not like",
            "regexp",
            "not regexp",
        ]

        operator = operators[0]

        value = None

        if (len(args)) >= 2:
            operator = args[0]
            value = args[1]
        elif len(args) == 1:
            value = args[0]

        if operator not in operators:
            raise ValueError("Invalid comparison operator. The operator can be %s" % ", ".join(operators))

        return operator, value
