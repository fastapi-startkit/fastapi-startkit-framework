from .plan import Plan, validate_destination


def write_plan(plan: Plan) -> None:
    validate_destination(plan.directory)
    plan.directory.mkdir(parents=True, exist_ok=True)
    for name, content in plan.files.items():
        path = plan.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    artisan = plan.directory / "artisan"
    artisan.chmod(artisan.stat().st_mode | 0o111)
