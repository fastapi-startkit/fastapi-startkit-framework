from fastapi import Depends
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia

from app.http.requests.organization import OrganizationListRequest
from app.models.Organization import Organization


async def index(filters: OrganizationListRequest = Depends()):
    paginator = await (
        Organization.query()
        .when(filters.search, lambda q: q.where("name", "like", f"%{filters.search}%"))
        .paginate(page=filters.page, per_page=filters.limit)
    )

    return Inertia.render(
        "Organizations/Index",
        {
            "data": [
                {
                    "id": org.id,
                    "name": org.name,
                    "phone": org.phone,
                    "city": org.city,
                    "deleted_at": None,
                }
                for org in paginator.result
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
    return Inertia.render("Organizations/Create")


async def store(request: Request):
    form = await request.json()
    form["account_id"] = 1  # hardcoded for demo
    await Organization.create(form)
    return RedirectResponse(url="/organizations", status_code=303)


async def edit(organization: str):
    org = await Organization.find(organization)
    return Inertia.render(
        "Organizations/Edit",
        {
            "organization": {
                "id": org.id,
                "name": org.name,
                "email": org.email,
                "phone": org.phone,
                "address": org.address,
                "city": org.city,
                "region": org.region,
                "country": org.country,
                "postal_code": org.postal_code,
                "deleted_at": None,
            }
        },
    )


async def update(request: Request, organization: str):
    org = await Organization.find(organization)
    form = await request.json()
    await org.update(form)
    return RedirectResponse(url=f"/organizations/{organization}/edit", status_code=303)


async def destroy(organization: str):
    org = await Organization.find(organization)
    await org.delete()
    return RedirectResponse(url="/organizations", status_code=303)
