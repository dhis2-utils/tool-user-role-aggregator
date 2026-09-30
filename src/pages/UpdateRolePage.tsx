import i18n from '@dhis2/d2-i18n'
import {
    Button,
    ButtonStrip,
    CircularLoader,
    NoticeBox,
    SingleSelectField,
    SingleSelectOption,
    Transfer,
} from '@dhis2/ui'
import React, { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './UpdateRolePage.module.css'
import { canManageRole } from '@/domain/userRole'
import { useAddAuthoritiesToRole } from '@/hooks/useAddAuthoritiesToRole'
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'
import { useUserRoles } from '@/hooks/useUserRoles'

export const UpdateRolePage = () => {
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

    const [selectedRoleId, setSelectedRoleId] = useState<string>()
    const [roleIdsToAdd, setRoleIdsToAdd] = useState<string[]>([])

    const { addAuthoritiesToRole, isUpdating } = useAddAuthoritiesToRole({
        onSuccess: () => setRoleIdsToAdd([]),
    })

    const selectedRole = userRoles?.find((role) => role.id === selectedRoleId)

    const { candidateRoles, hasRolesBeyondReach } = useMemo(() => {
        if (!userRoles || !selectedRole) {
            return {
                candidateRoles: [],
                hasRolesBeyondReach: false,
            }
        }
        const heldAuthorities = new Set(selectedRole.authorities ?? [])
        const otherRoles = userRoles.filter(
            (role) => role.id !== selectedRole.id
        )
        return {
            // Only roles the signed-in user could manage themselves: their
            // authorities are a subset of the user's own, so aggregating them
            // can never grant away an authority the user does not hold.
            candidateRoles: otherRoles.filter(
                (role) =>
                    !canManageRole(heldAuthorities, role) &&
                    canManageRole(myAuthorities, role)
            ),
            // Roles the selected role cannot manage and that the signed-in
            // user may not grant either — they are withheld, not absent, so
            // the empty state must not claim every role is already covered.
            hasRolesBeyondReach: otherRoles.some(
                (role) =>
                    !canManageRole(heldAuthorities, role) &&
                    !canManageRole(myAuthorities, role)
            ),
        }
    }, [userRoles, selectedRole, myAuthorities])

    if (isLoadingMe || isLoadingRoles) {
        return (
            <div className={styles.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const error = meError || rolesError
    if (error || !userRoles) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error?.message || i18n.t('An unknown error occurred')}
            </NoticeBox>
        )
    }

    const onSubmit = () => {
        if (!selectedRole || roleIdsToAdd.length === 0) {
            return
        }
        addAuthoritiesToRole({
            roleId: selectedRole.id,
            roleIdsToAdd,
        })
    }

    return (
        <div className={styles.card}>
            <h1 className={styles.title}>
                {i18n.t('Update existing user role')}
            </h1>
            <p className={styles.description}>
                {i18n.t(
                    'Select an existing role and extend it with the authorities of additional roles so its members can manage users with those roles as well. Use "Check what this role can manage" to see which roles it can currently manage.'
                )}
            </p>
            {selectedRole && (
                <p className={styles.checkLink}>
                    <Link to={`/?roles=${selectedRole.id}`}>
                        {i18n.t('Check what this role can manage')}
                    </Link>
                </p>
            )}
            <div className={styles.field}>
                <SingleSelectField
                    className={styles.roleSelect}
                    label={i18n.t('Existing role')}
                    selected={selectedRoleId}
                    onChange={({ selected }) => {
                        setSelectedRoleId(selected)
                        setRoleIdsToAdd([])
                    }}
                    filterable
                    noMatchText={i18n.t('No roles match the filter')}
                >
                    {userRoles.map((role) => (
                        <SingleSelectOption
                            key={role.id}
                            label={role.displayName}
                            value={role.id}
                        />
                    ))}
                </SingleSelectField>
            </div>
            {selectedRole && (
                <>
                    <h2 className={styles.sectionTitle}>
                        {i18n.t('Add managed roles')}
                    </h2>
                    {candidateRoles.length > 0 ? (
                        <>
                            <div className={styles.field}>
                                <span className={styles.fieldLabel}>
                                    {i18n.t(
                                        'The authorities of the selected roles will be added to {{role}}',
                                        {
                                            role: selectedRole.displayName,
                                            interpolation: {
                                                escapeValue: false,
                                            },
                                        }
                                    )}
                                </span>
                                {!isSuperuser && (
                                    <span className={styles.fieldHint}>
                                        {i18n.t(
                                            'Only roles whose authorities you hold yourself are listed.'
                                        )}
                                    </span>
                                )}
                                <Transfer
                                    options={candidateRoles.map((role) => ({
                                        label: role.displayName,
                                        value: role.id,
                                    }))}
                                    selected={roleIdsToAdd}
                                    onChange={({ selected }) =>
                                        setRoleIdsToAdd(selected)
                                    }
                                    filterable
                                    filterablePicked
                                    height="280px"
                                />
                            </div>
                            <ButtonStrip>
                                <Button
                                    primary
                                    onClick={onSubmit}
                                    loading={isUpdating}
                                    disabled={
                                        isUpdating || roleIdsToAdd.length === 0
                                    }
                                >
                                    {i18n.t('Add authorities to role')}
                                </Button>
                            </ButtonStrip>
                        </>
                    ) : (
                        <p className={styles.emptyText}>
                            {hasRolesBeyondReach
                                ? i18n.t(
                                      'There are no further roles you can add to this role. You can only add roles whose authorities you hold yourself.'
                                  )
                                : i18n.t(
                                      'This role already has the authorities of every other user role.'
                                  )}
                        </p>
                    )}
                </>
            )}
        </div>
    )
}
