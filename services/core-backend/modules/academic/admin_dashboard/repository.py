from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class AdminOverviewRecord:
    active_users_count: int
    configured_classrooms_count: int
    active_geofences_count: int


class AdminDashboardRepository:
    async def get_overview(self, connection: asyncpg.Connection) -> AdminOverviewRecord:
        row = await connection.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM identity.users WHERE account_status = 'active')
                    AS active_users_count,
                (SELECT COUNT(*) FROM academic.classrooms WHERE status = 'active')
                    AS configured_classrooms_count,
                (
                    SELECT COUNT(*) FROM academic.classrooms
                    WHERE status = 'active'
                      AND latitude IS NOT NULL
                      AND longitude IS NOT NULL
                      AND default_geofence_radius_m IS NOT NULL
                ) AS active_geofences_count
            """,
        )
        return AdminOverviewRecord(
            active_users_count=row["active_users_count"],
            configured_classrooms_count=row["configured_classrooms_count"],
            active_geofences_count=row["active_geofences_count"],
        )
