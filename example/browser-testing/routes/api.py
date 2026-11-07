from app.http.controllers import home_controller
from fastapi_startkit.fastapi import Router

router = Router()
router.get("/", home_controller.index)
router.get("/health", home_controller.health)
