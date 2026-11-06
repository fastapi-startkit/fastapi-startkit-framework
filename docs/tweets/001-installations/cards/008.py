app = Application(
    providers=[
        (LogProvider, LoggingConfig),
        (FastapiProvider, FastAPIConfig),
        (DatabaseProvider, DatabaseConfig),
        (ViteProvider, ViteConfig),
        InertiaProvider,
    ],
)
