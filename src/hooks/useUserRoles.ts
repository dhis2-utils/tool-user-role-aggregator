import { UserRole } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

interface UserRolesResponse {
    userRoles: UserRole[]
}

export const userRolesQueryKey = ['userRoles']

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
        cacheTime: Infinity,
        staleTime: Infinity,
    })

    return {
        userRoles: data?.userRoles,
        isLoading,
        error,
    }
}
