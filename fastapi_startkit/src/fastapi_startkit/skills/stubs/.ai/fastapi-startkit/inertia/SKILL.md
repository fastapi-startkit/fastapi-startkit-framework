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

## Request validation (Pydantic)

Type-hint a `RequestModel` parameter on a write method and FastAPI validates
the submitted form before your controller runs. `RequestModel` is a Pydantic
model, so use Pydantic types and `Field(...)` constraints — `EmailStr` for
emails, constrained `str`, `int`, optional/mixed fields, etc. Invalid input
raises a `ValidationError` (422) that Inertia surfaces back to the form's
`errors`.

```python
# app/http/requests/project_store_request.py
from typing import Optional

from pydantic import EmailStr, Field
from fastapi_startkit.fastapi import RequestModel


class ProjectStoreRequest(RequestModel):
    name: str = Field(min_length=2, max_length=120)   # required string, length-bounded
    owner_email: EmailStr                              # validated email
    budget: int = Field(ge=0)                          # integer, non-negative
    priority: int = Field(default=1, ge=1, le=5)       # mixed: optional with bounds
    description: Optional[str] = Field(default=None, max_length=500)
```

```python
# app/http/controllers/projects_controller.py
from fastapi.responses import RedirectResponse

from app.models import Project
from app.http.requests.project_store_request import ProjectStoreRequest


async def store(request: ProjectStoreRequest):
    await Project.create(request.model_dump())
    return RedirectResponse(url="/projects", status_code=303)
```

## Shared data

Use `Inertia.share()` to expose props on every page (e.g. the authenticated
user or flash messages) without repeating them in each controller.

```python
Inertia.share("auth", {"user": current_user})
Inertia.share({"flash": {"success": "Project updated."}})
```

# Frontend (React)

Pages live under `resources/js/Pages/` and are resolved by name in
`resources/js/app.tsx` via `createInertiaApp`. The `component` you pass to
`Inertia.render("Projects/Edit", ...)` maps to `Pages/Projects/Edit.tsx`, and
the controller's `props` arrive as the component's props.

```tsx
// resources/js/app.tsx
import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'

createInertiaApp({
  resolve: name => {
    const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
    return pages[`./Pages/${name}.tsx`]
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})
```

## Components & props

A page is a plain component that receives the controller's props. The shape
matches what the resource serialised on the server.

```tsx
// resources/js/Pages/Projects/Show.tsx
interface ProjectShowProps {
  project: { id: number; name: string; owner_email: string }
}

export default function Show({ project }: ProjectShowProps) {
  return (
    <>
      <h1>{project.name}</h1>
      <p>Owner: {project.owner_email}</p>
    </>
  )
}
```

## Persistent layouts

Assign a `layout` function on the page component so the layout instance is
**kept mounted** across Inertia visits (state, scroll position, etc. persist).

```tsx
// resources/js/Pages/Welcome.tsx
import Layout from './Layout'

const Welcome = ({ user }: { user: { name: string } }) => {
  return (
    <>
      <h1>Welcome</h1>
      <p>Hello {user.name}, welcome to your first Inertia app!</p>
    </>
  )
}

Welcome.layout = (page: React.ReactNode) => <Layout>{page}</Layout>

export default Welcome
```

## Inertia form helper — `useForm`

`useForm` is Inertia's form helper. It tracks `data`, exposes `setData`, the
verb methods (`get`/`post`/`put`/`patch`/`delete`), a `processing` flag, and
server-side `errors` (populated from a 422 `ValidationError`).

```tsx
// resources/js/Pages/Projects/Create.tsx
import { useForm } from '@inertiajs/react'
import Layout from './Layout'

const Create = () => {
  const { data, setData, post, processing, errors } = useForm({
    name: '',
    owner_email: '',
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    post('/projects', {
      onSuccess: () => console.log('created'),
    })
  }

  return (
    <form onSubmit={submit}>
      <input
        value={data.name}
        onChange={e => setData('name', e.target.value)}
      />
      {errors.name && <div>{errors.name}</div>}

      <input
        type="email"
        value={data.owner_email}
        onChange={e => setData('owner_email', e.target.value)}
      />
      {errors.owner_email && <div>{errors.owner_email}</div>}

      <button type="submit" disabled={processing}>Save</button>
    </form>
  )
}

Create.layout = (page: React.ReactNode) => <Layout>{page}</Layout>

export default Create
```

`useForm` also drives reactive requests like search-as-you-type — call a verb
method on change and read `processing` for the in-flight state:

```tsx
import { useForm } from '@inertiajs/react'

export default function Search() {
  const { data, setData, get, processing } = useForm({ query: '' })

  function search(e: React.ChangeEvent<HTMLInputElement>) {
    setData('query', e.target.value)
    get('/search', {
      preserveState: true,
      onSuccess: () => console.log('done'),
    })
  }

  return (
    <>
      <input value={data.query} onChange={search} />
      {processing && <div>Searching…</div>}
    </>
  )
}
```

## Inertia HTTP helper — `router`

For programmatic visits outside a form, use the `router` helper. It performs
Inertia visits (`get`/`post`/`put`/`patch`/`delete`/`visit`/`reload`) and
accepts the same options (`preserveState`, `preserveScroll`, `only`,
`onSuccess`, …).

```tsx
import { router } from '@inertiajs/react'

// navigate
router.get('/projects')

// submit data, then reload only specific props
router.post('/projects', { name: 'New' }, {
  preserveScroll: true,
  onSuccess: () => router.reload({ only: ['projects'] }),
})

// delete with a confirmation
function destroy(id: number) {
  router.delete(`/projects/${id}`)
}
```
