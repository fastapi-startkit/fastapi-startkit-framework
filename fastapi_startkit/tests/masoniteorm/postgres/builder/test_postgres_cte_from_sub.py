from ...sqlite.builder.test_sqlite_cte_from_sub import CteFromSubCases
from ..fixtures.db import schema
from ..test_case import TestCase


class TestPostgresCteFromSub(CteFromSubCases, TestCase):
    schema = schema
