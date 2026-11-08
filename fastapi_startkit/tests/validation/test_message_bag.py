from fastapi_startkit.validation import MessageBag, ValidationException


def test_empty_bag():
    bag = MessageBag()

    assert not bag.any()
    assert bag.count() == 0
    assert bag.first() is None
    assert bag.to_dict() == {"message": "The given data was invalid.", "errors": {}}


def test_add_get_first_and_has():
    bag = MessageBag().add("email", "Taken.").add("email", "Invalid.").add("name", "Required.")

    assert bag.has("email")
    assert not bag.has("password")
    assert bag.get("email") == ["Taken.", "Invalid."]
    assert bag.get("password") == []
    assert bag.first("name") == "Required."
    assert bag.first() == "Taken."
    assert bag.all() == ["Taken.", "Invalid.", "Required."]


def test_summary_counts_remaining_errors():
    assert MessageBag({"a": ["One."]}).summary() == "One."
    assert MessageBag({"a": ["One.", "Two."]}).summary() == "One. (and 1 more error)"
    assert MessageBag({"a": ["One."], "b": ["Two.", "Three."]}).to_dict() == {
        "message": "One. (and 2 more errors)",
        "errors": {"a": ["One."], "b": ["Two.", "Three."]},
    }


def test_merge():
    bag = MessageBag({"a": ["One."]}).merge(MessageBag({"a": ["Two."], "b": ["Three."]}))

    assert bag.messages == {"a": ["One.", "Two."], "b": ["Three."]}


def test_from_errors_joins_locations_and_skips_prefix():
    errors = [
        {"loc": ("body", "address", "street"), "msg": "Required."},
        {"loc": ("body", "items", 0), "msg": "Invalid."},
    ]

    assert MessageBag.from_errors(errors, skip=1).messages == {
        "address.street": ["Required."],
        "items.0": ["Invalid."],
    }


def test_string_messages_are_single_messages():
    bag = MessageBag({"email": "Taken.", "name": ["Short.", "Odd."]})

    assert bag.messages == {"email": ["Taken."], "name": ["Short.", "Odd."]}
    assert ValidationException({"email": "Taken."}).errors == {"email": ["Taken."]}
