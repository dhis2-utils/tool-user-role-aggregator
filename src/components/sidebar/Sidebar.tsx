import i18n from '@dhis2/d2-i18n'
import { IconChevronLeft24 } from '@dhis2/ui'
import cx from 'classnames'
import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import styles from './Sidebar.module.css'
import { Sidenav, SidenavHeading, SidenavItems, SidenavLink } from './sidenav'
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'

type LinkItem = { to: string; label: string }

const SidebarNavLink = ({ to, label, end }: LinkItem & { end?: boolean }) => (
    <SidenavLink to={to} label={label} end={end} LinkComponent={NavLink} />
)

export const Sidebar = ({ className }: { className?: string }) => {
    const [collapsed, setCollapsed] = useState(false)
    const { canAddUserRoles, canViewUsers } = useCurrentUserAuthorities()

    return (
        <aside
            className={cx(styles.asideWrapper, className, {
                [styles.collapsed]: collapsed,
            })}
        >
            <Sidenav>
                <SidenavItems>
                    <SidenavHeading>{i18n.t('Check access')}</SidenavHeading>
                    <SidebarNavLink
                        to="/"
                        label={i18n.t('Role combination')}
                        end
                    />
                    {canViewUsers && (
                        <SidebarNavLink
                            to="/check-user"
                            label={i18n.t('Look up user')}
                        />
                    )}
                    {canAddUserRoles && (
                        <>
                            <SidenavHeading>
                                {i18n.t('Manage roles')}
                            </SidenavHeading>
                            <SidebarNavLink
                                to="/create"
                                label={i18n.t('Create new role')}
                            />
                            <SidebarNavLink
                                to="/update"
                                label={i18n.t('Update existing role')}
                            />
                        </>
                    )}
                </SidenavItems>
            </Sidenav>
            <button
                className={styles.collapseButton}
                type="button"
                onClick={() => setCollapsed(!collapsed)}
            >
                <div
                    className={cx(styles.iconWrapper, {
                        [styles.collapsed]: collapsed,
                    })}
                >
                    <IconChevronLeft24 />
                </div>
            </button>
        </aside>
    )
}
