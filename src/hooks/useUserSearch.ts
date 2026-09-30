import { UserRole } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

export const MIN_QUERY_LENGTH = 2

export interface SearchedUser {
    id: string
    displayName: string
    username?: string
    userRoles: UserRole[]
}

interface UsersResponse {
    users: SearchedUser[]
}

/**
 * Users matching a name or username fragment, with their roles and each
 * role's authorities, so manageability can be computed without extra calls.
 */
export const useUserSearch = (query: string) => {
    const trimmed = query.trim()
    const isActive = trimmed.length >= MIN_QUERY_LENGTH
    const { data, isLoading, error } = useApiDataQuery<UsersResponse>({
        queryKey: ['users', 'search', trimmed],
        query: {
            resource: 'users',
            params: {
                query: trimmed,
                fields: 'id,displayName,username,userRoles[id,displayName,authorities]',
                order: 'displayName:asc',
                pageSize: 10,
            },
        },
        enabled: isActive,
        keepPreviousData: true,
    })

    // A disabled query keeps status 'loading' (fetchStatus 'idle'), so
    // isLoading is true whenever the query is inactive — gate it on
    // isActive too. keepPreviousData restores the previous result set once
    // the key changes to the disabled/empty query, so also withhold users
    // while inactive, or a cleared search would keep showing stale rows.
    return {
        users: isActive ? data?.users : undefined,
        isLoading: isActive && isLoading,
        error,
    }
}
