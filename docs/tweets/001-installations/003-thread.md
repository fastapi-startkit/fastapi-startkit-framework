# Tweet 3/10

Everything is a provider. Bind services in `register()`, then resolve them in `boot()` once every provider has registered 📦

Card: `providers/app_provider.py`

```python
from fastapi_startkit.support import Provider

class AppProvider(Provider):
    def register(self) -> None:
        self.app.bind("billing", BillingService)

    def boot(self) -> None:
        billing = self.app.make("billing")
        billing.connect()
```
