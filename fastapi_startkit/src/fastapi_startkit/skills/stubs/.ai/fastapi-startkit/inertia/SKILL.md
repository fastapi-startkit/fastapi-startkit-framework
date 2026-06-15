---
name: fastapi-startkit-inertia
description: Building server-driven SPA pages with Inertia.js + FastAPI in fastapi-startkit (render, props, resources, forms, redirects, shared data).
---

# Inertia + FastAPI

[Inertia.js](https://inertiajs.com/) lets you build a single-page app using
classic server-side routing and controllers. In fastapi-startkit you return an
`InertiaResponse` from a controller and Inertia renders the matching client
page component (Vue/React/Svelte) with the props you pass.

## Setup

Inertia ships as a provider. Register `InertiaProvider` and add
`InertiaMiddleware` to the app so `InertiaResponse` can negotiate full-page vs
XHR (partial) requests.

```python
from fastapi_startkit.inertia import Inertia, InertiaMiddleware, InertiaProvider
```

## Rendering a page

Use the `Inertia` facade. `Inertia.render(component, props)` returns an
`InertiaResponse`; `component` is the client-side page name (e.g.
`"Projects/Edit"`), `props` is a plain dict serialised to the page.

```python
# app/http/controllers/projects_controller.py
from fastapi_startkit.inertia import Inertia, InertiaResponse

from app.models import Project
from app.http.resources.project_resource import ProjectResource


async def edit(project: int) -> InertiaResponse:
    p = await Project.find_or_fail(project)
    return Inertia.render("Projects/Edit", {
        "project": ProjectResource(p).serialize(),
    })
```

Pair resources with Inertia to keep the shape you send to the front-end
consistent. `ProjectResource` is a `JsonResource`; call `.serialize()` to get a
plain dict suitable for props.

## A resourceful Inertia controller

Inertia controllers follow the same resourceful method names as the rest of the
framework (`index`, `create`, `store`, `show`, `edit`, `update`, `destroy`).
GET methods render a page; write methods persist and then **redirect** (Inertia
expects a 303 redirect after `store`/`update`/`destroy`, not a JSON body).

```python
# app/http/controllers/projects_controller.py
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia, InertiaResponse

from app.models import Project
from app.http.resources.project_resource import ProjectResource


async def index() -> InertiaResponse:
    projects = await Project.all()
    return Inertia.render("Projects/Index", {
        "projects": [ProjectResource(p).serialize() for p in projects],
    })


async def create() -> InertiaResponse:
    return Inertia.render("Projects/Create")


async def store(request: Request):
    form = await request.json()
    await Project.create(form)
    return RedirectResponse(url="/projects", status_code=303)


async def show(project: int) -> InertiaResponse:
    p = await Project.find_or_fail(project)
    return Inertia.render("Projects/Show", {
        "project": ProjectResource(p).serialize(),
    })


async def edit(project: int) -> InertiaResponse:
    p = await Project.find_or_fail(project)
    return Inertia.render("Projects/Edit", {
        "project": ProjectResource(p).serialize(),
    })


async def update(project: int, request: Request):
    p = await Project.find_or_fail(project)
    await p.update(await request.json())
    return RedirectResponse(url=f"/projects/{project}/edit", status_code=303)


async def destroy(project: int):
    p = await Project.find_or_fail(project)
    await p.delete()
    return RedirectResponse(url="/projects", status_code=303)
```

Register the routes with `router.resource()`:

```python
# routes/web.py
from fastapi_startkit.fastapi import Router

from app.http.controllers import projects_controller

router = Router()
router.resource("projects", projects_controller)
```

## Shared data

Use `Inertia.share()` to expose props on every page (e.g. the authenticated
user or flash messages) without repeating them in each controller.

```python
Inertia.share("auth", {"user": current_user})
Inertia.share({"flash": {"success": "Project updated."}})
```
