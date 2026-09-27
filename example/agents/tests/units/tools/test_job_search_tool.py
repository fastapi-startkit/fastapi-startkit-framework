"""job_search_tool filters by keyword and, when given, by work mode.

Regression: an onsite search used to return remote roles because work_mode was
accepted but never applied.
"""

import unittest

from app.constants.work_mode import WorkMode
from app.tools.job_search_tool import job_search_tool


def _ids(rows: list) -> list[int]:
    return sorted(job["id"] for job in rows)


def _search(query: str, work_mode: str | None = None) -> list:
    args = {"query": query}
    if work_mode is not None:
        args["work_mode"] = work_mode
    return job_search_tool.invoke(args)


class TestJobSearchTool(unittest.TestCase):
    def test_onsite_returns_only_onsite_roles(self):
        results = _search("jobs", WorkMode.ON_SITE)
        self.assertTrue(results)
        self.assertTrue(all(job["work_mode"] == WorkMode.ON_SITE for job in results))
        self.assertNotIn(WorkMode.REMOTE, [job["work_mode"] for job in results])

    def test_remote_returns_only_remote_roles(self):
        results = _search("jobs", WorkMode.REMOTE)
        self.assertTrue(results)
        self.assertTrue(all(job["work_mode"] == WorkMode.REMOTE for job in results))

    def test_no_work_mode_returns_the_whole_board(self):
        # A noise-only query with no work mode is "show me everything".
        self.assertEqual(_ids(_search("jobs")), [1, 2, 3, 4, 5])

    def test_keyword_and_work_mode_combine(self):
        # "developer" keyword within remote roles matches the Python Developer only.
        results = _search("developer", WorkMode.REMOTE)
        self.assertEqual(_ids(results), [2])

    def test_keyword_narrows_within_a_work_mode(self):
        # A keyword that no onsite role matches yields nothing, not a remote role.
        self.assertEqual(_search("python", WorkMode.ON_SITE), [])


if __name__ == "__main__":
    unittest.main()
