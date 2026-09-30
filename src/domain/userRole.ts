import { AUTHORITY_ALL, UserRole } from '../types/userRole'

/** Lets a user administer any user. */
export const AUTHORITY_USER_ADD = 'F_USER_ADD'
/** Lets a user administer only users in user groups they manage. */
export const AUTHORITY_USER_ADD_IN_GROUP = 'F_USER_ADD_WITHIN_MANAGED_GROUP'
/** Required to list and read users. */
export const AUTHORITY_USER_VIEW = 'F_USER_VIEW'
/** Either of these lets a user create or change user roles. */
export const USERROLE_ADD_AUTHORITIES = [
    'F_USERROLE_PRIVATE_ADD',
    'F_USERROLE_PUBLIC_ADD',
]

/**
 * A role is manageable by someone holding `heldAuthorities` when every
 * authority of the role is included in the held set (the DHIS2 user
 * management rule: you may only manage users with equal or fewer
 * privileges than yourself).
 */
export const canManageRole = (
    heldAuthorities: ReadonlySet<string>,
    role: UserRole
): boolean => {
    if (heldAuthorities.has(AUTHORITY_ALL)) {
        return true
    }
    const roleAuthorities = role.authorities ?? []
    if (roleAuthorities.includes(AUTHORITY_ALL)) {
        return false
    }
    return roleAuthorities.every((authority) => heldAuthorities.has(authority))
}

/**
 * Whether a user holding `heldAuthorities` may grant `authorityId` — a
 * superuser (holder of `ALL`) implicitly holds every authority. Used to
 * limit the authority picker to the current user's own authorities.
 */
export const canGrantAuthority = (
    heldAuthorities: ReadonlySet<string>,
    authorityId: string
): boolean =>
    heldAuthorities.has(AUTHORITY_ALL) || heldAuthorities.has(authorityId)

/** Union of the authorities of every given role. */
export const aggregateAuthorities = (roles: UserRole[]): Set<string> =>
    new Set(roles.flatMap((role) => role.authorities ?? []))

/**
 * Whether the holder can administer users at all. Without one of these
 * authorities, "which roles can this set manage" has no meaning: the holder
 * cannot administer anybody, however many other authorities they have.
 */
export const canAdministerUsers = (
    heldAuthorities: ReadonlySet<string>
): boolean =>
    heldAuthorities.has(AUTHORITY_ALL) ||
    heldAuthorities.has(AUTHORITY_USER_ADD) ||
    heldAuthorities.has(AUTHORITY_USER_ADD_IN_GROUP)

/** Whether a single role confers user administration. Drives the picker badge. */
export const isUserAdminRole = (role: UserRole): boolean =>
    canAdministerUsers(new Set(role.authorities ?? []))

/** The role's authorities the holder lacks, sorted for stable display. */
export const missingAuthorities = (
    heldAuthorities: ReadonlySet<string>,
    role: UserRole
): string[] => {
    if (heldAuthorities.has(AUTHORITY_ALL)) {
        return []
    }
    return (role.authorities ?? [])
        .filter((authority) => !heldAuthorities.has(authority))
        .sort((a, b) => a.localeCompare(b))
}

export interface BlockedRole {
    role: UserRole
    missing: string[]
}

export interface ManageabilityReport {
    /** False when the set holds no user-administration authority. */
    canAdminister: boolean
    /** True when administration is confined to managed user groups. */
    limitedToManagedGroups: boolean
    manageable: UserRole[]
    blocked: BlockedRole[]
}

/**
 * Which of `allRoles` a holder of `heldAuthorities` may manage. When the
 * holder cannot administer users at all, both lists are empty — listing
 * roles would imply an ability that does not exist.
 */
export const manageabilityReport = (
    heldAuthorities: ReadonlySet<string>,
    allRoles: UserRole[]
): ManageabilityReport => {
    const canAdminister = canAdministerUsers(heldAuthorities)
    const limitedToManagedGroups =
        heldAuthorities.has(AUTHORITY_USER_ADD_IN_GROUP) &&
        !heldAuthorities.has(AUTHORITY_USER_ADD) &&
        !heldAuthorities.has(AUTHORITY_ALL)

    if (!canAdminister) {
        return {
            canAdminister,
            limitedToManagedGroups,
            manageable: [],
            blocked: [],
        }
    }

    const manageable: UserRole[] = []
    const blocked: BlockedRole[] = []
    for (const role of allRoles) {
        if (canManageRole(heldAuthorities, role)) {
            manageable.push(role)
        } else {
            blocked.push({
                role,
                missing: missingAuthorities(heldAuthorities, role),
            })
        }
    }
    return { canAdminister, limitedToManagedGroups, manageable, blocked }
}
