from markupsafe import Markup
from fastapi_startkit.support import Provider
from .encoding import html_safe_json
from .inertia import Inertia
from .middleware import InertiaMiddleware


class InertiaProvider(Provider):
    provider_key = "inertia"

    def register(self) -> None:
        self.app.bind("inertia", Inertia)

    def boot(self) -> None:
        self.app.add_middleware(InertiaMiddleware)

        if self.app.has("templates"):
            templates = self.app.make("templates")

            def inertia_helper(page):
                client_page = {key: value for key, value in page.items() if key != "ssr"}
                encoded_page = html_safe_json(client_page)
                ssr_body = page.get("ssr", {}).get("body", "")
                return Markup(
                    f'<script data-page="app" type="application/json">{encoded_page}</script><div id="app">{ssr_body}</div>'
                )

            def inertia_head(page):
                head = page.get("ssr", {}).get("head", [])
                if isinstance(head, str):
                    head = [head]
                return Markup("".join(str(item) for item in head))

            templates.env.globals["inertia"] = inertia_helper
            templates.env.globals["inertia_head"] = inertia_head
            templates.env.globals["Inertia"] = self.app.make("inertia")
