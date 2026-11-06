from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", session.create)

auth = Router(dependencies=[Depends(auth)])
auth.resource("organizations", organizations_controller)
