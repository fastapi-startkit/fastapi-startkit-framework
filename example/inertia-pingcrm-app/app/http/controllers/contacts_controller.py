from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia
from app.http.requests.contact import (
    ContactListRequest,
    ContactStoreRequest,
    ContactUpdateRequest,
)
from app.models.Contact import Contact
from app.models.Organization import Organization


async def index(filters: ContactListRequest = Depends()):
    paginator = await (
        Contact.query()
        .when(
            filters.search,
            lambda q: q.where("first_name", "like", f"%{filters.search}%").or_where(
                "last_name", "like", f"%{filters.search}%"
            ),
        )
        .paginate(page=filters.page, per_page=filters.limit)
    )

    return Inertia.render(
        "Contacts/Index",
        {
            "data": [
                {
                    "id": c.id,
                    "name": f"{c.first_name} {c.last_name}",
                    "organization_id": c.organization_id,
                    "organization": None,
                    "city": c.city,
                    "phone": c.phone,
                    "deleted_at": None,
                }
                for c in paginator.result
            ],
            "meta": {
                "current_page": paginator.current_page,
                "last_page": paginator.last_page,
                "per_page": paginator.per_page,
                "total": paginator.total,
            },
        },
    )


async def create():
    organizations = await Organization.query().limit(100).get()
    return Inertia.render(
        "Contacts/Create",
        {"organizations": [{"id": o.id, "name": o.name} for o in organizations]},
    )


async def store(form: ContactStoreRequest):
    await Contact.create(form.model_dump())
    return RedirectResponse(url="/contacts", status_code=303)


async def edit(contact: str):
    c = await Contact.find(contact)
    organizations = await Organization.query().limit(100).get()
    return Inertia.render(
        "Contacts/Edit",
        {
            "contact": {
                "id": c.id,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "organization_id": c.organization_id,
                "email": c.email,
                "phone": c.phone,
                "address": c.address,
                "city": c.city,
                "region": c.region,
                "country": c.country,
                "postal_code": c.postal_code,
                "deleted_at": None,
            },
            "organizations": [{"id": o.id, "name": o.name} for o in organizations],
        },
    )


async def update(form: ContactUpdateRequest, contact: str):
    c = await Contact.find(contact)
    await c.update(form.model_dump(exclude_none=True))
    return RedirectResponse(url=f"/contacts/{contact}/edit", status_code=303)


async def destroy(contact: str):
    c = await Contact.find(contact)
    await c.delete()
    return RedirectResponse(url="/contacts", status_code=303)
