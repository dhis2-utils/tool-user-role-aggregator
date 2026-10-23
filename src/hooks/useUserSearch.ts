import type { UserRole } from '@/types/userRole'
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
    pager?: { total?: number }
}

/** How many matches the search shows; the total is reported alongside. */
export const SEARCH_PAGE_SIZE = 10

/**
 * Users matching a name or username fragment, with their roles and each
 * role's authorities, so manageability can be computed without extra calls.
 */
export const useUserSearch = (query: string) => {
    const trimmed = query.trim()
    const isActive = trimmed.length >= MIN_QUERY_LENGTH
    const { data, isLoading, isPreviousData, error } =
        useApiDataQuery<UsersResponse>({
            queryKey: ['users', 'search', trimmed],
            query: {
                resource: 'users',
                params: {
                    query: trimmed,
                    fields: 'id,displayName,username,userRoles[id,displayName,authorities]',
                    order: 'displayName:asc',
                    pageSize: SEARCH_PAGE_SIZE,
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
    // For the same reason, while a new search is in flight the previous
    // search's rows are withheld and the search counts as loading, so
    // nobody can pick a user from the old result set.
    const isCurrent = isActive && !isPreviousData
    return {
        users: isCurrent ? data?.users : undefined,
        total: isCurrent ? data?.pager?.total : undefined,
        isLoading: isActive && (isLoading || isPreviousData),
        error,
    }
}
