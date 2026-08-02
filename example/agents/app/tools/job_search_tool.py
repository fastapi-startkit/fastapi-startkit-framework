from langchain_core.tools import tool

from app.constants.work_mode import WorkMode

jobs = [
    {
        "id": 1,
        "title": "Software Engineer",
        "work_mode": WorkMode.REMOTE,
        "location": "San Francisco",
        "company": "Acme Corp",
        "type": "Full-time",
    },
    {
        "id": 2,
        "title": "Python Developer",
        "work_mode": WorkMode.REMOTE,
        "location": "Remote",
        "company": "Startup Inc",
        "type": "Full-time",
    },
    {
        "id": 3,
        "title": "Data Scientist",
        "work_mode": WorkMode.ON_SITE,
        "location": "New York",
        "company": "DataCo",
        "type": "Full-time",
    },
    {
        "id": 4,
        "title": "DevOps Engineer",
        "work_mode": WorkMode.ON_SITE,
        "location": "Austin",
        "company": "CloudBase",
        "type": "Contract",
    },
    {
        "id": 5,
        "title": "Product Manager",
        "work_mode": WorkMode.REMOTE,
        "location": "Remote",
        "company": "ProductHQ",
        "type": "Full-time",
    },
]


# Generic words that describe "a job" rather than which job — searching them
# would match nothing even though the user clearly wants to see openings.
NOISE_TERMS = {"job", "jobs", "role", "roles", "position", "positions", "opening", "openings", "work", "career"}


@tool(description="Use this tools if user wants to search for jobs")
def job_search_tool(query: str, work_mode: WorkMode | None = None) -> list:
    """Searches for jobs by keyword and, when given, narrows to a work mode
    (remote / onsite / hybrid). Supports wildcards (* and ?) in each query term.
    Omit work_mode when the user hasn't asked for a specific one."""
    import fnmatch

    results = jobs
    if work_mode is not None:
        results = [job for job in results if job.get("work_mode") == work_mode]

    patterns = [f"*{term}*" for term in query.lower().split() if term not in NOISE_TERMS]
    if patterns:
        # A blank or all-noise query ("jobs") means "show me the board" — keep the
        # work-mode-filtered set as-is; only narrow further on real keywords.
        results = [
            job
            for job in results
            if any(fnmatch.fnmatch(" ".join(str(v) for v in job.values()).lower(), pattern) for pattern in patterns)
        ]

    return results
