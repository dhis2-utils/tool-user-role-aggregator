import i18n from '@dhis2/d2-i18n'
import {
    Button,
    ButtonStrip,
    CircularLoader,
    InputField,
    NoticeBox,
    Transfer,
} from '@dhis2/ui'
import { zodResolver } from '@hookform/resolvers/zod'
import React, { useMemo } from 'react'
import { useForm, Controller, useWatch } from 'react-hook-form'
import { z } from 'zod'
import styles from './CreateRolePage.module.css'
import {
    canAdministerUsers,
    canGrantAuthority,
    canManageRole,
} from '@/domain/userRole'
import { useCreateUserRole } from '@/hooks/useCreateUserRole'
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'
import { useSystemAuthorities } from '@/hooks/useSystemAuthorities'
import { useUserRoles } from '@/hooks/useUserRoles'
import { SystemAuthority, UserRole } from '@/types/userRole'

/** Authorities most user administrator roles need, preselected for convenience */
const DEFAULT_AUTHORITIES = [
    'F_USER_ADD',
    'F_USER_DELETE',
    'M_dhis-web-user',
    'F_USER_VIEW',
]

// Built lazily (inside the component) so validation messages are
// translated after the platform has set the user's locale.
const buildSchema = () =>
    z
        .object({
            name: z.string().min(1, i18n.t('Role name is required')),
            rolesToManage: z.array(z.string()),
            additionalAuthorities: z.array(z.string()),
        })
        .refine(
            (values) =>
                values.rolesToManage.length > 0 ||
                values.additionalAuthorities.length > 0,
            {
                message: i18n.t(
                    'Select at least one role to manage or one additional authority'
                ),
                path: ['rolesToManage'],
            }
        )

type FormValues = z.infer<ReturnType<typeof buildSchema>>

const CreateRoleForm = ({
    manageableRoles,
    systemAuthorities,
    isSuperuser,
}: {
    manageableRoles: UserRole[]
    systemAuthorities: SystemAuthority[]
    isSuperuser: boolean
}) => {
    const schema = useMemo(buildSchema, [])
    const { control, handleSubmit, reset } = useForm<FormValues>({
        resolver: zodResolver(schema),
        defaultValues: {
            name: '',
            rolesToManage: [],
            additionalAuthorities: DEFAULT_AUTHORITIES.filter((id) =>
                systemAuthorities.some((authority) => authority.id === id)
            ),
        },
    })

    const { createUserRole, isCreating } = useCreateUserRole({
        onSuccess: () => reset(),
    })

    const watchedRoles = useWatch({ control, name: 'rolesToManage' })
    const watchedAuthorities = useWatch({
        control,
        name: 'additionalAuthorities',
    })
    const resultingAuthorities = useMemo(() => {
        const fromRoles = manageableRoles
            .filter((role) => (watchedRoles ?? []).includes(role.id))
            .flatMap((role) => role.authorities ?? [])
        return new Set([...(watchedAuthorities ?? []), ...fromRoles])
    }, [manageableRoles, watchedRoles, watchedAuthorities])
    const willAdministerUsers = canAdministerUsers(resultingAuthorities)

    const onSubmit = (values: FormValues) => {
        const selectedRoles = manageableRoles.filter((role) =>
            values.rolesToManage.includes(role.id)
        )

        createUserRole({
            name: values.name,
            description: i18n.t(
                'Admin role for managing users with roles: {{roles}}',
                {
                    roles: selectedRoles
                        .map((role) => role.displayName)
                        .join(', '),
                    nsSeparator: '###',
                    interpolation: { escapeValue: false },
                }
            ),
            roleIdsToManage: values.rolesToManage,
            additionalAuthorities: values.additionalAuthorities,
        })
    }

    const roleOptions = manageableRoles.map((role) => ({
        label: role.displayName,
        value: role.id,
    }))
    const authorityOptions = systemAuthorities.map((authority) => ({
        label: authority.name,
        value: authority.id,
    }))

    return (
        <form onSubmit={handleSubmit(onSubmit)}>
            <Controller
                name="name"
                control={control}
                render={({ field, fieldState }) => (
                    <div className={styles.field}>
                        <InputField
                            className={styles.nameInput}
                            label={i18n.t('Role name')}
                            placeholder={i18n.t('Enter new role name')}
                            value={field.value}
                            onChange={({ value }) =>
                                field.onChange(value ?? '')
                            }
                            onBlur={field.onBlur}
                            error={!!fieldState.error}
                            validationText={fieldState.error?.message}
                            required
                        />
                    </div>
                )}
            />
            <Controller
                name="rolesToManage"
                control={control}
                render={({ field, fieldState }) => (
                    <div className={styles.field}>
                        <span className={styles.fieldLabel}>
                            {i18n.t('User roles to manage')}
                        </span>
                        <Transfer
                            options={roleOptions}
                            selected={field.value}
                            onChange={({ selected }) =>
                                field.onChange(selected)
                            }
                            filterable
                            filterablePicked
                            height="280px"
                        />
                        {fieldState.error && (
                            <span className={styles.fieldError}>
                                {fieldState.error.message}
                            </span>
                        )}
                    </div>
                )}
            />
            <Controller
                name="additionalAuthorities"
                control={control}
                render={({ field }) => (
                    <div className={styles.field}>
                        <span className={styles.fieldLabel}>
                            {i18n.t('Additional authorities')}
                        </span>
                        {!isSuperuser && (
                            <span className={styles.fieldHint}>
                                {i18n.t(
                                    'Only authorities you hold yourself are listed.'
                                )}
                            </span>
                        )}
                        <Transfer
                            options={authorityOptions}
                            selected={field.value}
                            onChange={({ selected }) =>
                                field.onChange(selected)
                            }
                            filterable
                            filterablePicked
                            height="280px"
                        />
                    </div>
                )}
            />
            {resultingAuthorities.size > 0 && !willAdministerUsers && (
                <div className={styles.field}>
                    <NoticeBox
                        warning
                        title={i18n.t('This role cannot administer users')}
                    >
                        {i18n.t(
                            'None of the selected roles or authorities grants Add/Update User, so members of this role will not be able to manage other users.',
                            { nsSeparator: '###' }
                        )}
                    </NoticeBox>
                </div>
            )}
            <ButtonStrip>
                <Button
                    type="submit"
                    primary
                    loading={isCreating}
                    disabled={isCreating}
                >
                    {i18n.t('Create role')}
                </Button>
            </ButtonStrip>
        </form>
    )
}

export const CreateRolePage = () => {
    const {
        authorities: myAuthorities,
        isSuperuser,
        isLoading: isLoadingMe,
        error: meError,
    } = useCurrentUserAuthorities()
    const {
        userRoles,
        isLoading: isLoadingRoles,
        error: rolesError,
    } = useUserRoles()
    const {
        authorities: systemAuthorities,
        isLoading: isLoadingAuthorities,
        error: authoritiesError,
    } = useSystemAuthorities()
    if (isLoadingMe || isLoadingRoles || isLoadingAuthorities) {
        return (
            <div className={styles.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const error = meError || rolesError || authoritiesError
    if (error || !userRoles || !systemAuthorities) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error?.message || i18n.t('An unknown error occurred')}
            </NoticeBox>
        )
    }

    const manageableRoles = userRoles.filter((role) =>
        canManageRole(myAuthorities, role)
    )
    // A user must not be able to grant authorities they do not hold
    // themselves, so the picker only offers their own authorities.
    const grantableAuthorities = systemAuthorities.filter((authority) =>
        canGrantAuthority(myAuthorities, authority.id)
    )

    return (
        <div className={styles.card}>
            <h1 className={styles.title}>
                {i18n.t('Create new user admin role')}
            </h1>
            <p className={styles.description}>
                {i18n.t(
                    'Create a user role for user administrators: users who should manage other users. Pick the roles the administrator should be able to manage, and the new role will be given all authorities of those roles. This follows the DHIS2 user management concept that requires a user to have the same or more privileges than the users they manage.',
                    { nsSeparator: '###' }
                )}
            </p>
            <CreateRoleForm
                manageableRoles={manageableRoles}
                systemAuthorities={grantableAuthorities}
                isSuperuser={isSuperuser}
            />
        </div>
    )
}
