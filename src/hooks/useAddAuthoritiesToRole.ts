import { useDataEngine, useAlert } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchRoleAuthorities } from './fetchRoleAuthorities'
import { userRolesQueryKey } from './useUserRoles'

export interface AddAuthoritiesPayload {
    roleId: string
    /** Roles whose authorities should be added to the target role */
    roleIdsToAdd: string[]
}

type UseAddAuthoritiesToRoleOptions = {
    onSuccess?: () => void
}

/**
 * Adds the authorities of the given source roles to an existing user
 * role. Both the target role (with its owner fields, so the PUT contains
 * the complete object) and the source roles' authorities are fetched at
 * submit time, so the merge is based on fresh data.
 */
export const useAddAuthoritiesToRole = ({
    onSuccess,
}: UseAddAuthoritiesToRoleOptions = {}) => {
    const dataEngine = useDataEngine()
    const queryClient = useQueryClient()

    const { show: showSuccessAlert } = useAlert(
        i18n.t('User role updated successfully'),
        { success: true }
    )
    const { show: showErrorAlert } = useAlert(
        ({ message }: { message: string }) =>
            i18n.t('Failed to update user role: {{message}}', {
                message,
                nsSeparator: '###',
            }),
        { critical: true }
    )

    const { mutate: addAuthoritiesToRole, isLoading: isUpdating } = useMutation<
        unknown,
        Error,
        AddAuthoritiesPayload
    >(
        async ({ roleId, roleIdsToAdd }) => {
            const [{ userRole }, authoritiesToAdd] = await Promise.all([
                dataEngine.query({
                    userRole: {
                        resource: 'userRoles',
                        id: roleId,
                        params: { fields: ':owner' },
                    },
                }) as Promise<{ userRole: { authorities?: string[] } }>,
                fetchRoleAuthorities(dataEngine, roleIdsToAdd),
            ])

            const mergedAuthorities = new Set([
                ...(userRole.authorities ?? []),
                ...authoritiesToAdd,
            ])

            return dataEngine.mutate({
                resource: 'userRoles',
                id: roleId,
                type: 'update',
                data: {
                    ...userRole,
                    authorities: Array.from(mergedAuthorities),
                },
            })
        },
        {
            onSuccess: () => {
                showSuccessAlert()
                queryClient.invalidateQueries({
                    queryKey: userRolesQueryKey,
                })
                onSuccess?.()
            },
            onError: (error) => {
                showErrorAlert({ message: error.message })
            },
        }
    )

    return {
        addAuthoritiesToRole,
        isUpdating,
    }
}
