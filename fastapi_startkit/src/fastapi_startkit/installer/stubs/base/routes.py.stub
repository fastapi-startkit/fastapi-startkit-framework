from app.http.controllers.home_controller import HomeController
from fastapi_startkit.fastapi import Router

controller = HomeController()
router = Router()
router.get("/", controller.index, response_model=None)
router.get("/health", controller.health)
