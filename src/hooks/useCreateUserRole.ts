import { useDataEngine, useAlert } from '@dhis2/app-runtime'
import i18n from '@dhis2/d2-i18n'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchRoleAuthorities } from './fetchRoleAuthorities'
import { mutationErrorMessage } from './mutationErrorMessage'
import { userRolesQueryKey } from './useUserRoles'
import { ungrantableAuthorities } from '@/domain/userRole'

export interface CreateUserRolePayload {
    name: string
    description: string
    /** Roles whose authorities the new role aggregates */
    roleIdsToManage: string[]
    additionalAuthorities: string[]
}

interface UseCreateUserRoleOptions {
    /** The signed-in user's authorities; nothing beyond them is granted. */
    heldAuthorities: ReadonlySet<string>
    onSuccess?: () => void
}

export const useCreateUserRole = ({
    heldAuthorities,
    onSuccess,
}: UseCreateUserRoleOptions) => {
    const dataEngine = useDataEngine()
    const queryClient = useQueryClient()

    const { show: showSuccessAlert } = useAlert(
        i18n.t('User role created successfully'),
        { success: true }
    )
    const { show: showErrorAlert } = useAlert(
        ({ message }: { message: string }) =>
            i18n.t('Failed to create user role: {{message}}', {
                message,
                nsSeparator: '###',
                // Shown as plain text in the alert, so nothing to escape.
                interpolation: { escapeValue: false },
            }),
        { critical: true }
    )

    const { mutate: createUserRole, isLoading: isCreating } = useMutation<
        unknown,
        Error,
        CreateUserRolePayload
    >(
        async ({
            name,
            description,
            roleIdsToManage,
            additionalAuthorities,
        }) => {
            // Fetch the source roles' authorities at submit time — the
            // cached list may be stale if another admin edited roles since
            // the page was loaded.
            const roleAuthorities = await fetchRoleAuthorities(
                dataEngine,
                roleIdsToManage,
                heldAuthorities
            )
            const ungrantable = ungrantableAuthorities(
                heldAuthorities,
                additionalAuthorities
            )
            if (ungrantable.length > 0) {
                throw new Error(
                    i18n.t(
                        'You do not hold these authorities and cannot grant them: {{authorities}}',
                        {
                            authorities: ungrantable.join(', '),
                            nsSeparator: '###',
                            interpolation: { escapeValue: false },
                        }
                    )
                )
            }
            const aggregated = new Set([
                ...additionalAuthorities,
                ...roleAuthorities,
            ])
            return dataEngine.mutate({
                resource: 'userRoles',
                type: 'create',
                data: {
                    name,
                    description,
                    authorities: [...aggregated],
                },
            })
        },
        {
            onSuccess: () => {
                showSuccessAlert()
                queryClient.invalidateQueries({ queryKey: userRolesQueryKey })
                onSuccess?.()
            },
            onError: (error) => {
                showErrorAlert({ message: mutationErrorMessage(error) })
            },
        }
    )

    return {
        createUserRole,
        isCreating,
    }
}
