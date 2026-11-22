class EagerRelations:
    def __init__(self, relation=None):
        self.eagers = []
        self.nested_eagers = {}
        self.callback_eagers = {}
        self.is_nested = False
        self.relation = relation

    def register(self, *relations, callback=None):
        for relation in relations:
            if isinstance(relation, str) and "." not in relation:
                self.eagers += [relation]
            elif isinstance(relation, str) and "." in relation:
                self.is_nested = True
                relation_key, _, nested = relation.partition(".")
                self.nested_eagers.setdefault(relation_key, []).append(nested)
            elif isinstance(relation, (tuple, list)):
                for eagers in relations:
                    for eager in eagers:
                        self.register(eager)
            elif isinstance(relation, dict):
                self.callback_eagers.update(relation)

        return self

    def get_eagers(self):
        eagers = []
        if self.eagers:
            eagers.append(self.eagers)

        if self.nested_eagers:
            eagers.append(self.nested_eagers)

        if self.callback_eagers:
            eagers.append(self.callback_eagers)

        return eagers
