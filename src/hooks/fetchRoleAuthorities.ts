import type { useDataEngine } from '@dhis2/app-runtime'

type DataEngine = ReturnType<typeof useDataEngine>

interface RoleAuthoritiesResponse {
    roles: {
        userRoles: Array<{ id: string; authorities?: string[] }>
    }
}

/**
 * Fetches the current authorities of the given roles directly from the
 * server, so aggregation is based on fresh data rather than the cached
 * role list (which may be stale if roles were edited elsewhere).
 */
export const fetchRoleAuthorities = async (
    dataEngine: DataEngine,
    roleIds: string[]
): Promise<string[]> => {
    if (roleIds.length === 0) {
        return []
    }
    const { roles } = (await dataEngine.query({
        roles: {
            resource: 'userRoles',
            params: {
                filter: `id:in:[${roleIds.join(',')}]`,
                fields: 'id,authorities',
                paging: false,
            },
        },
    })) as unknown as RoleAuthoritiesResponse
    return roles.userRoles.flatMap((role) => role.authorities ?? [])
}
