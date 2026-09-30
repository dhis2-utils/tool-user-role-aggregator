import { SystemAuthority } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

interface AuthoritiesResponse {
    systemAuthorities: SystemAuthority[]
}

/**
 * All authorities known to the system. The endpoint is not paged and
 * returns `{ systemAuthorities: [{ id, name }] }` on all supported
 * DHIS2 versions (2.40+).
 */
export const useSystemAuthorities = () => {
    const { data, isLoading, error } = useApiDataQuery<AuthoritiesResponse>({
        queryKey: ['authorities'],
        query: {
            resource: 'authorities',
        },
        cacheTime: Infinity,
        staleTime: Infinity,
    })

    return {
        authorities: data?.systemAuthorities,
        isLoading,
        error,
    }
}
