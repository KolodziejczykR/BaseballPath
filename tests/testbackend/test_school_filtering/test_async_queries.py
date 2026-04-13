import pytest

from backend.school_filtering.database.async_queries import AsyncSchoolDataQueries
from backend.utils.school_group_constants import POWER_4_D1


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, name, rows):
        self.name = name
        self.rows = rows
        self._in_filters = {}
        self._neq_filters = {}
        self._require_not_null = set()
        self._negated = False

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, _column, _value):
        return self

    def neq(self, column, value):
        self._neq_filters[column] = value
        return self

    @property
    def not_(self):
        self._negated = True
        return self

    def is_(self, column, value):
        if self._negated and value == "null":
            self._require_not_null.add(column)
        self._negated = False
        return self

    def in_(self, column, values):
        self._in_filters[column] = set(values)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        rows = list(self.rows)
        for column, value in self._neq_filters.items():
            rows = [row for row in rows if row.get(column) != value]
        for column in self._require_not_null:
            rows = [row for row in rows if row.get(column) is not None]
        for column, values in self._in_filters.items():
            rows = [row for row in rows if row.get(column) in values]
        return _FakeResponse(rows)


class _FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _FakeTable(name, self.tables.get(name, []))


class _FakeConnection:
    def __init__(self, client):
        self.client = client

    async def execute_with_retry(self, func, *args):
        return await func(self.client, *args)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_load_division_group_cache_loads_all_mappings_with_team_name():
    client = _FakeClient(
        {
            "school_baseball_ranking_name_mapping": [
                {
                    "school_name": "Kansas State University",
                    "team_name": "Kansas St",
                    "verified": None,
                },
                {
                    "school_name": "Oregon State University",
                    "team_name": "Oregon St",
                    "verified": True,
                },
            ],
            "baseball_rankings_data": [
                {
                    "team_name": "Kansas St",
                    "year": 2025,
                    "division": 1,
                    "division_group": "Power 4 D1",
                    "overall_rating": 40.0,
                    "offensive_rating": 38.0,
                    "defensive_rating": 42.0,
                    "power_rating": 41.0,
                    "strength_of_schedule": 75.0,
                },
                {
                    "team_name": "Oregon St",
                    "year": 2025,
                    "division": 1,
                    "division_group": "Power 4 D1",
                    "overall_rating": 45.0,
                    "offensive_rating": 43.0,
                    "defensive_rating": 47.0,
                    "power_rating": 46.0,
                    "strength_of_schedule": 72.0,
                },
            ],
        }
    )
    queries = AsyncSchoolDataQueries(connection=_FakeConnection(client))

    await queries._load_division_group_cache()

    assert queries._division_group_cache["Kansas State University"]["division_group"] == POWER_4_D1
    assert queries._division_group_cache["Oregon State University"]["division_group"] == POWER_4_D1
