import i18n from '@dhis2/d2-i18n'
import { CircularLoader, InputField, NoticeBox, Tag } from '@dhis2/ui'
import React, { useMemo, useState } from 'react'
import styles from './CheckUserPage.module.css'
import { ManageabilityReport } from '@/components/ManageabilityReport'
import { aggregateAuthorities, isUserAdminRole } from '@/domain/userRole'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useSystemAuthorities } from '@/hooks/useSystemAuthorities'
import { useUserRoles } from '@/hooks/useUserRoles'
import type { SearchedUser } from '@/hooks/useUserSearch'
import {
    MIN_QUERY_LENGTH,
    SEARCH_PAGE_SIZE,
    useUserSearch,
} from '@/hooks/useUserSearch'

const SearchResults = ({
    users,
    total,
    isSearching,
    onSelect,
}: {
    users?: SearchedUser[]
    total?: number
    isSearching: boolean
    onSelect: (user: SearchedUser) => void
}) => (
    <>
        {isSearching && <CircularLoader />}

        {users?.length === 0 && (
            <p className={styles.emptyText}>
                {i18n.t('No users match that search.')}
            </p>
        )}

        {users && users.length > 0 && (
            <ul className={styles.resultList}>
                {users.map((user) => (
                    <li key={user.id}>
                        <button
                            type="button"
                            className={styles.resultButton}
                            onClick={() => onSelect(user)}
                        >
                            {user.displayName}
                            {user.username && (
                                <span className={styles.username}>
                                    {user.username}
                                </span>
                            )}
                        </button>
                    </li>
                ))}
            </ul>
        )}

        {users && total !== undefined && total > users.length && (
            <p className={styles.emptyText}>
                {i18n.t(
                    'Showing the first {{shown}} of {{total}} matches. Type more of the name to narrow the search.',
                    { shown: SEARCH_PAGE_SIZE, total }
                )}
            </p>
        )}
    </>
)

export const CheckUserPage = () => {
    const [query, setQuery] = useState('')
    const [selectedUser, setSelectedUser] = useState<SearchedUser>()
    const debouncedQuery = useDebouncedValue(query, 300)

    const {
        users,
        total,
        isLoading: isSearching,
        error: searchError,
    } = useUserSearch(debouncedQuery)
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

    const userAuthorities = useMemo(
        () => aggregateAuthorities(selectedUser?.userRoles ?? []),
        [selectedUser]
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
            <h1 className={styles.title}>{i18n.t('Look up a user')}</h1>
            <p className={styles.description}>
                {i18n.t(
                    'Search for a user to see which user roles they can manage, based on the authorities of all their roles combined.',
                    { nsSeparator: '###' }
                )}
            </p>

            <div className={styles.field}>
                <InputField
                    className={styles.search}
                    label={i18n.t('Search by name or username')}
                    value={query}
                    onChange={({ value }) => {
                        setQuery(value ?? '')
                        setSelectedUser(undefined)
                    }}
                    placeholder={i18n.t('At least {{n}} characters', {
                        n: MIN_QUERY_LENGTH,
                    })}
                />
            </div>

            {searchError && (
                <NoticeBox error title={i18n.t('Search failed')}>
                    {searchError.message}
                </NoticeBox>
            )}

            {!selectedUser && (
                <SearchResults
                    users={users}
                    total={total}
                    isSearching={isSearching}
                    onSelect={setSelectedUser}
                />
            )}

            {selectedUser && (
                <>
                    <h2 className={styles.sectionTitle}>
                        {selectedUser.displayName}
                    </h2>
                    <ul className={styles.roleList}>
                        {selectedUser.userRoles.map((role) => (
                            <li key={role.id}>
                                {role.displayName}{' '}
                                {isUserAdminRole(role) && (
                                    <Tag positive>{i18n.t('user admin')}</Tag>
                                )}
                            </li>
                        ))}
                    </ul>
                    <ManageabilityReport
                        authorities={userAuthorities}
                        roleCount={selectedUser.userRoles.length}
                        allRoles={userRoles}
                        systemAuthorities={systemAuthorities}
                    />
                </>
            )}
        </div>
    )
}
