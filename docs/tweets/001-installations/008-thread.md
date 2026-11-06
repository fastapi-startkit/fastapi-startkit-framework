# Tweet 8/10

Need a frontend? Add the Vite and Inertia providers and write React pages with hot reload. It's still FastAPI underneath 🎨

Card: `bootstrap/application.py`

```python
app = Application(
    providers=[
        (LogProvider, LoggingConfig),
        (FastapiProvider, FastAPIConfig),
        (DatabaseProvider, DatabaseConfig),
        (ViteProvider, ViteConfig),
        InertiaProvider,
    ],
)
```
