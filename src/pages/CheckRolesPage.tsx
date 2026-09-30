import i18n from '@dhis2/d2-i18n'
import {
    CircularLoader,
    NoticeBox,
    Tag,
    Transfer,
    TransferOption,
} from '@dhis2/ui'
import React, { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import styles from './CheckRolesPage.module.css'
import { ManageabilityReport } from '@/components/ManageabilityReport'
import { aggregateAuthorities, isUserAdminRole } from '@/domain/userRole'
import { useSystemAuthorities } from '@/hooks/useSystemAuthorities'
import { useUserRoles } from '@/hooks/useUserRoles'

const ROLES_PARAM = 'roles'

export const CheckRolesPage = () => {
    const [searchParams, setSearchParams] = useSearchParams()
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

    const selectedIds = useMemo(() => {
        const raw = searchParams.get(ROLES_PARAM)
        const requested = raw ? raw.split(',').filter(Boolean) : []
        const known = new Set((userRoles ?? []).map((role) => role.id))
        // Ignore ids that are not roles visible to this user
        return requested.filter((id) => known.has(id))
    }, [searchParams, userRoles])

    const setSelectedIds = (ids: string[]) => {
        const next = new URLSearchParams(searchParams)
        if (ids.length > 0) {
            next.set(ROLES_PARAM, ids.join(','))
        } else {
            next.delete(ROLES_PARAM)
        }
        setSearchParams(next, { replace: true })
    }

    const sortedRoles = useMemo(() => {
        const roles = [...(userRoles ?? [])]
        // user-admin roles first, then the API's displayName order
        return roles.sort(
            (a, b) => Number(isUserAdminRole(b)) - Number(isUserAdminRole(a))
        )
    }, [userRoles])

    const adminRoleIds = useMemo(
        () =>
            new Set(
                (userRoles ?? []).filter(isUserAdminRole).map((role) => role.id)
            ),
        [userRoles]
    )

    const selectedRoles = useMemo(
        () => (userRoles ?? []).filter((role) => selectedIds.includes(role.id)),
        [userRoles, selectedIds]
    )
    const combinedAuthorities = useMemo(
        () => aggregateAuthorities(selectedRoles),
        [selectedRoles]
    )

    if (isLoadingRoles || isLoadingAuthorities) {
        return (
            <div className={styles.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const error = rolesError || authoritiesError
    if (error || !userRoles || !systemAuthorities) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error?.message || i18n.t('An unknown error occurred')}
            </NoticeBox>
        )
    }

    return (
        <div className={styles.card}>
            <h1 className={styles.title}>
                {i18n.t('Check what a role combination can manage')}
            </h1>
            <p className={styles.description}>
                {i18n.t(
                    'Pick the roles a user holds. Their authorities are combined, because a user administers other users with everything their roles grant together, not with one role at a time.',
                    { nsSeparator: '###' }
                )}
            </p>

            <div className={styles.field}>
                <span className={styles.fieldLabel}>
                    {i18n.t('User roles held')}
                </span>
                <Transfer
                    options={sortedRoles.map((role) => ({
                        label: role.displayName,
                        value: role.id,
                    }))}
                    selected={selectedIds}
                    onChange={({ selected }) => setSelectedIds(selected)}
                    renderOption={(option) => (
                        <TransferOption
                            {...option}
                            label={
                                <span className={styles.option}>
                                    {option.label}
                                    {adminRoleIds.has(option.value) && (
                                        <Tag positive>
                                            {i18n.t('user admin')}
                                        </Tag>
                                    )}
                                </span>
                            }
                        />
                    )}
                    filterable
                    filterablePicked
                    height="280px"
                />
            </div>

            {selectedIds.length === 0 ? (
                <p className={styles.emptyText}>
                    {i18n.t(
                        'Select one or more roles to see what they can manage.'
                    )}
                </p>
            ) : (
                <ManageabilityReport
                    authorities={combinedAuthorities}
                    roleCount={selectedRoles.length}
                    allRoles={userRoles}
                    systemAuthorities={systemAuthorities}
                />
            )}
        </div>
    )
}
