from fastapi import Depends
from fastapi_startkit_auth import Auth

from app.http.controllers import dashboard_controller, login_controller, register_controller
from fastapi_startkit.fastapi import Router

router = Router()
router.get("/register", register_controller.create)
router.post("/register", register_controller.store)
router.get("/login", login_controller.create)
router.post("/login", login_controller.store)
router.post("/logout", login_controller.destroy)

authenticated = Router(dependencies=[Depends(Auth.guard("web"))])
authenticated.get("/dashboard", dashboard_controller.index)
