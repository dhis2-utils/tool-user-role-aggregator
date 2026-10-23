import type { UserRole } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

interface UserRolesResponse {
    userRoles: UserRole[]
}

export const userRolesQueryKey = ['userRoles']

const ROLES_STALE_TIME_MS = 60_000

/**
 * All user roles in the system, including their authorities so that
 * "who can manage whom" can be computed client side.
 */
export const useUserRoles = () => {
    const { data, isLoading, error } = useApiDataQuery<UserRolesResponse>({
        queryKey: userRolesQueryKey,
        query: {
            resource: 'userRoles',
            params: {
                fields: 'id,displayName,authorities',
                order: 'displayName:asc',
                paging: false,
            },
        },
        // Roles change in other apps too. Refetch when the page is
        // revisited or the window regains focus, at most once a minute,
        // so the verdicts do not stay stale for a whole session.
        staleTime: ROLES_STALE_TIME_MS,
    })

    return {
        userRoles: data?.userRoles,
        isLoading,
        error,
    }
}
