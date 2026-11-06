from fastapi_startkit.support import Provider

class AppProvider(Provider):
    def register(self) -> None:
        self.app.bind("billing", BillingService)

    def boot(self) -> None:
        billing = self.app.make("billing")
        billing.connect()
