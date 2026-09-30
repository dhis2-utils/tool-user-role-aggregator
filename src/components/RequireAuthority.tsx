import i18n from '@dhis2/d2-i18n'
import { CircularLoader, NoticeBox } from '@dhis2/ui'
import React from 'react'
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'
import { AUTHORITY_ALL } from '@/types/userRole'

interface RequireAuthorityProps {
    /** The page renders when the user holds any of these, or ALL. */
    anyOf: string[]
    children: React.ReactNode
}

/**
 * Renders its children only for users holding one of `anyOf`. Pages behind
 * this guard need no permission checks of their own.
 */
export const RequireAuthority = ({
    anyOf,
    children,
}: RequireAuthorityProps) => {
    const { authorities, isLoading, error } = useCurrentUserAuthorities()

    if (isLoading) {
        return <CircularLoader />
    }
    if (error) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error.message}
            </NoticeBox>
        )
    }

    const allowed =
        authorities.has(AUTHORITY_ALL) ||
        anyOf.some((authority) => authorities.has(authority))

    if (!allowed) {
        return (
            <NoticeBox warning title={i18n.t('Missing permissions')}>
                {i18n.t(
                    'This page needs one of these authorities: {{authorities}}',
                    { authorities: anyOf.join(', '), nsSeparator: '###' }
                )}
            </NoticeBox>
        )
    }

    return <>{children}</>
}
