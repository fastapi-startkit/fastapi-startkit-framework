from langchain_core.tools import tool

jobs = [
    {"id": 1, "title": "Software Engineer", "location": "San Francisco", "company": "Acme Corp", "type": "Full-time"},
    {"id": 2, "title": "Frontend Developer", "location": "Remote", "company": "Startup Inc", "type": "Full-time"},
    {"id": 3, "title": "Data Scientist", "location": "New York", "company": "DataCo", "type": "Full-time"},
    {"id": 4, "title": "DevOps Engineer", "location": "Austin", "company": "CloudBase", "type": "Contract"},
    {"id": 5, "title": "Product Manager", "location": "Remote", "company": "ProductHQ", "type": "Full-time"},
]


@tool(description="Use this tools if user wants to search for jobs")
def job_search_tool(query: str) -> list:
    """Searches for jobs based on the given query. Supports wildcards (* and ?) in each term."""
    import fnmatch

    patterns = [f"*{term}*" for term in query.lower().split()]

    return [
        job
        for job in jobs
        if any(fnmatch.fnmatch(" ".join(str(v) for v in job.values()).lower(), pattern) for pattern in patterns)
    ]
