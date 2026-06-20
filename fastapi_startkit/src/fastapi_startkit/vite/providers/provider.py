import os


from fastapi_startkit.providers import Provider
from ..config.vite import ViteConfig

from ..vite import Vite


class ViteProvider(Provider):
    provider_key = "vite"

    def register(self) -> None:
        from ..config.vite import ViteConfig

        config = self.resolve_config(ViteConfig)
        self.merge_config_from(config, self.provider_key)

        config = ViteConfig(**config)

        vite = Vite(
            public_path=config.public_path,
            build_directory=config.build_directory,
            hot_file=config.hot_file,
            manifest_filename=config.manifest_filename,
            asset_url=config.asset_url,
        )

        self.app.bind("vite", vite)

        self.register_templates(config)

    def register_templates(self, config: ViteConfig) -> None:
        # Provide a template engine out of the box so fresh apps can render
        # views and have the vite() globals injected during boot. An existing
        # binding always wins, keeping this backward-compatible.
        if not config.template or self.app.has("templates"):
            return

        try:
            from starlette.templating import Jinja2Templates
        except ImportError as exc:
            raise ImportError(
                "Rendering templates requires Jinja2. Install it with: pip install fastapi-startkit[vite]"
            ) from exc

        templates_dir = self.app.base_path / config.templates_directory
        self.app.bind("templates", Jinja2Templates(directory=str(templates_dir)))

    def boot(self) -> None:
        vite: Vite = self.app.make("vite")
        config = self.app.make("config").get(self.provider_key)
        config = ViteConfig(**config)

        self.mount_static_file_if_require(config)
        self.register_jinja_directives(vite)

        source = os.path.abspath(str(os.path.join(str(os.path.dirname(__file__)), "../config/vite.py")))
        self.publishes({source: "config/vite.py"})

        stubs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../stubs"))

        self.publishes(
            {
                os.path.join(stubs_path, "vite.config.ts"): "vite.config.ts",
                os.path.join(stubs_path, "package.json"): "package.json",
                os.path.join(stubs_path, "tsconfig.json"): "tsconfig.json",
                os.path.join(stubs_path, "resources/js/app.ts"): "resources/js/app.ts",
                os.path.join(stubs_path, "resources/css/app.css"): "resources/css/app.css",
                os.path.join(stubs_path, "templates/index.html"): "templates/index.html",
            }
        )

    def mount_static_file_if_require(self, config: ViteConfig):
        if config.mount_static:
            build_path = os.path.join(config.public_path, config.build_directory)
            if os.path.isdir(build_path):
                try:
                    from fastapi.staticfiles import StaticFiles

                    self.app.fastapi.mount(
                        config.static_url,
                        StaticFiles(directory=build_path),
                        name="vite_assets",
                    )
                except ImportError:
                    pass  # fastapi optional dependency not installed

    def register_jinja_directives(self, vite: Vite):
        # Wire up Jinja2 globals when a template object is registered.
        # Wrap HTML-returning helpers in Markup so Jinja2 does not escape the tags.
        if self.app.has("templates"):
            templates = self.app.make("templates")
            if hasattr(templates, "env"):
                try:
                    from markupsafe import Markup
                except ImportError:
                    Markup = str  # type: ignore[assignment,misc]

                templates.env.globals["vite"] = lambda *a, **kw: Markup(vite(*a, **kw))
                templates.env.globals["vite_asset"] = vite.asset
                templates.env.globals["vite_react_refresh"] = lambda: Markup(vite.react_refresh())
