# Tweet 5/10

`Router` wraps FastAPI's APIRouter and adds `resource()`. One line gives you all seven CRUD routes 🛣️

Card: `routes/web.py`

```python
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", session.create)

auth = Router(dependencies=[Depends(auth)])
auth.resource("organizations", organizations_controller)
```
