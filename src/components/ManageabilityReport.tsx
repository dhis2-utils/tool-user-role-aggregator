import i18n from '@dhis2/d2-i18n'
import { Button, NoticeBox } from '@dhis2/ui'
import React, { useMemo, useState } from 'react'
import styles from './ManageabilityReport.module.css'
import {
    AUTHORITY_USER_ADD,
    AUTHORITY_USER_ADD_IN_GROUP,
    manageabilityReport,
} from '@/domain/userRole'
import { AUTHORITY_ALL, SystemAuthority, UserRole } from '@/types/userRole'

const MISSING_PREVIEW_COUNT = 5

/**
 * Which authority lets this set administer users, for the verdict line.
 * Only meaningful when the set can administer users at all.
 */
const administeringAuthority = (authorities: ReadonlySet<string>): string => {
    if (authorities.has(AUTHORITY_ALL)) {
        return AUTHORITY_ALL
    }
    if (authorities.has(AUTHORITY_USER_ADD)) {
        return AUTHORITY_USER_ADD
    }
    return AUTHORITY_USER_ADD_IN_GROUP
}

interface ManageabilityReportProps {
    /** The subject's combined authorities. */
    authorities: ReadonlySet<string>
    /** How many roles the authorities were aggregated from. */
    roleCount: number
    allRoles: UserRole[]
    systemAuthorities: SystemAuthority[]
}

const MissingAuthorities = ({
    missing,
    nameOf,
}: {
    missing: string[]
    nameOf: (id: string) => string
}) => {
    const [expanded, setExpanded] = useState(false)
    const shown = expanded ? missing : missing.slice(0, MISSING_PREVIEW_COUNT)
    const hidden = missing.length - shown.length

    return (
        <span className={styles.missing}>
            {i18n.t('missing {{n}}', { n: missing.length })}
            {': '}
            {shown.map((id) => nameOf(id)).join(', ')}
            {hidden > 0 && !expanded && (
                <Button small secondary onClick={() => setExpanded(true)}>
                    {i18n.t('show {{n}} more', { n: hidden })}
                </Button>
            )}
        </span>
    )
}

export const ManageabilityReport = ({
    authorities,
    roleCount,
    allRoles,
    systemAuthorities,
}: ManageabilityReportProps) => {
    const report = useMemo(
        () => manageabilityReport(authorities, allRoles),
        [authorities, allRoles]
    )
    const nameOf = useMemo(() => {
        const names = new Map(systemAuthorities.map((a) => [a.id, a.name]))
        return (id: string) => names.get(id) ?? id
    }, [systemAuthorities])

    const grantedBy = administeringAuthority(authorities)

    return (
        <div className={styles.report}>
            <p className={styles.summary}>
                {i18n.t(
                    'Roles: {{roles}} · Authorities: {{authorities}} combined',
                    {
                        roles: roleCount,
                        authorities: authorities.size,
                        nsSeparator: '###',
                    }
                )}
            </p>

            {!report.canAdminister ? (
                <NoticeBox warning title={i18n.t('Cannot administer users')}>
                    {i18n.t(
                        'None of these roles grants an authority for administering users, so this combination cannot manage any users regardless of its other authorities. Add/Update User is the authority that grants it.',
                        { nsSeparator: '###' }
                    )}
                </NoticeBox>
            ) : (
                <>
                    <p className={styles.verdict}>
                        {i18n.t('Can administer users, via {{authority}}', {
                            authority: nameOf(grantedBy),
                            nsSeparator: '###',
                            interpolation: { escapeValue: false },
                        })}
                    </p>
                    {report.limitedToManagedGroups && (
                        <NoticeBox
                            title={i18n.t('Limited to managed user groups')}
                        >
                            {i18n.t(
                                'This combination can only administer users in user groups it manages. Whether a given user falls inside those groups depends on user-group configuration, which this tool does not evaluate.',
                                { nsSeparator: '###' }
                            )}
                        </NoticeBox>
                    )}

                    <h3 className={styles.listTitle}>
                        {i18n.t('Can manage ({{n}})', {
                            n: report.manageable.length,
                        })}
                    </h3>
                    {report.manageable.length > 0 ? (
                        <ul
                            className={styles.roleList}
                            data-test="can-manage-list"
                        >
                            {report.manageable.map((role) => (
                                <li key={role.id}>{role.displayName}</li>
                            ))}
                        </ul>
                    ) : (
                        <p className={styles.emptyText}>
                            {i18n.t('No user roles can be managed.')}
                        </p>
                    )}

                    <h3 className={styles.listTitle}>
                        {i18n.t('Cannot manage ({{n}})', {
                            n: report.blocked.length,
                        })}
                    </h3>
                    {report.blocked.length > 0 ? (
                        <ul
                            className={styles.roleList}
                            data-test="cannot-manage-list"
                        >
                            {report.blocked.map(({ role, missing }) => (
                                <li key={role.id}>
                                    {role.displayName}{' '}
                                    <MissingAuthorities
                                        missing={missing}
                                        nameOf={nameOf}
                                    />
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className={styles.emptyText}>
                            {i18n.t('All user roles can be managed.')}
                        </p>
                    )}
                </>
            )}
        </div>
    )
}
