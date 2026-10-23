import type { useDataEngine } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import { ungrantableAuthorities } from '@/domain/userRole'

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
 *
 * The pickers only offer roles the user could grant, but that was decided
 * on the cached list. Throws if a role has since gained an authority the
 * user does not hold, or is gone, so the result can never grant away more
 * than the user's own authorities.
 */
export const fetchRoleAuthorities = async (
    dataEngine: DataEngine,
    roleIds: string[],
    heldAuthorities: ReadonlySet<string>
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
    if (roles.userRoles.length !== new Set(roleIds).size) {
        throw new Error(
            i18n.t(
                'One or more of the selected roles no longer exist. Reload the page and try again.'
            )
        )
    }
    const authorities = roles.userRoles.flatMap(
        (role) => role.authorities ?? []
    )
    const ungrantable = ungrantableAuthorities(heldAuthorities, authorities)
    if (ungrantable.length > 0) {
        throw new Error(
            i18n.t(
                'A selected role now has authorities you do not hold ({{authorities}}). Reload the page and try again.',
                {
                    authorities: ungrantable.join(', '),
                    interpolation: { escapeValue: false },
                }
            )
        )
    }
    return authorities
}
