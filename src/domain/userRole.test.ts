import { AUTHORITY_ALL } from '../types/userRole'
import type { UserRole } from '../types/userRole'
import {
    aggregateAuthorities,
    canAdministerUsers,
    canGrantAuthority,
    canManageRole,
    isUserAdminRole,
    manageabilityReport,
    missingAuthorities,
} from './userRole'

const role = (authorities?: string[]): UserRole => ({
    id: 'r1',
    displayName: 'Role',
    authorities,
})

describe('canManageRole', () => {
    it('allows a superuser (ALL) to manage any role', () => {
        const held = new Set([AUTHORITY_ALL])
        expect(canManageRole(held, role(['F_ANYTHING']))).toBe(true)
        expect(canManageRole(held, role([AUTHORITY_ALL]))).toBe(true)
        expect(canManageRole(held, role(undefined))).toBe(true)
    })

    it('allows managing a role whose authorities are a subset of the held set', () => {
        const held = new Set(['F_A', 'F_B', 'F_C'])
        expect(canManageRole(held, role(['F_A']))).toBe(true)
        expect(canManageRole(held, role(['F_A', 'F_C']))).toBe(true)
    })

    it('rejects a role with an authority the holder lacks', () => {
        const held = new Set(['F_A', 'F_B'])
        expect(canManageRole(held, role(['F_A', 'F_X']))).toBe(false)
    })

    it('rejects a superuser role for non-superuser holders', () => {
        const held = new Set(['F_A', 'F_B'])
        expect(canManageRole(held, role([AUTHORITY_ALL]))).toBe(false)
        expect(canManageRole(held, role([AUTHORITY_ALL, 'F_A']))).toBe(false)
    })

    it('treats a role without authorities as manageable by anyone', () => {
        const held = new Set<string>()
        expect(canManageRole(held, role(undefined))).toBe(true)
        expect(canManageRole(held, role([]))).toBe(true)
    })
})

describe('canGrantAuthority', () => {
    it('lets a superuser (ALL) grant any authority', () => {
        const held = new Set([AUTHORITY_ALL])
        expect(canGrantAuthority(held, 'F_ANYTHING')).toBe(true)
        expect(canGrantAuthority(held, AUTHORITY_ALL)).toBe(true)
    })

    it('lets a user grant an authority they hold', () => {
        expect(canGrantAuthority(new Set(['F_A', 'F_B']), 'F_A')).toBe(true)
    })

    it('rejects an authority the user does not hold', () => {
        expect(canGrantAuthority(new Set(['F_A']), 'F_B')).toBe(false)
        expect(canGrantAuthority(new Set(['F_A']), AUTHORITY_ALL)).toBe(false)
        expect(canGrantAuthority(new Set<string>(), 'F_A')).toBe(false)
    })
})

describe('aggregateAuthorities', () => {
    it('unions the authorities of several roles and de-duplicates', () => {
        const result = aggregateAuthorities([
            role(['F_A', 'F_B']),
            role(['F_B', 'F_C']),
        ])
        expect([...result].sort((a, b) => a.localeCompare(b))).toEqual([
            'F_A',
            'F_B',
            'F_C',
        ])
    })

    it('ignores roles without authorities', () => {
        expect(aggregateAuthorities([role(undefined), role([])]).size).toBe(0)
    })
})

describe('canAdministerUsers', () => {
    it('is true for ALL, F_USER_ADD, or the managed-group variant', () => {
        expect(canAdministerUsers(new Set([AUTHORITY_ALL]))).toBe(true)
        expect(canAdministerUsers(new Set(['F_USER_ADD']))).toBe(true)
        expect(
            canAdministerUsers(new Set(['F_USER_ADD_WITHIN_MANAGED_GROUP']))
        ).toBe(true)
    })

    it('is false without any user-administration authority', () => {
        expect(canAdministerUsers(new Set(['F_USER_VIEW', 'F_A']))).toBe(false)
        expect(canAdministerUsers(new Set<string>())).toBe(false)
    })
})

describe('isUserAdminRole', () => {
    it('detects roles that confer user administration', () => {
        expect(isUserAdminRole(role(['F_USER_ADD']))).toBe(true)
        expect(isUserAdminRole(role([AUTHORITY_ALL]))).toBe(true)
        expect(isUserAdminRole(role(['F_USER_VIEW']))).toBe(false)
        expect(isUserAdminRole(role(undefined))).toBe(false)
    })
})

describe('missingAuthorities', () => {
    it('returns the role authorities the holder lacks, sorted', () => {
        const held = new Set(['F_B'])
        expect(missingAuthorities(held, role(['F_C', 'F_A', 'F_B']))).toEqual([
            'F_A',
            'F_C',
        ])
    })

    it('returns nothing for a superuser', () => {
        expect(
            missingAuthorities(new Set([AUTHORITY_ALL]), role(['F_A']))
        ).toEqual([])
    })

    it('reports ALL as missing for a non-superuser', () => {
        expect(
            missingAuthorities(new Set(['F_A']), role([AUTHORITY_ALL]))
        ).toEqual([AUTHORITY_ALL])
    })
})

describe('manageabilityReport', () => {
    const named = (id: string, authorities?: string[]): UserRole => ({
        id,
        displayName: id,
        authorities,
    })

    it('reports nothing manageable when the set cannot administer users', () => {
        const report = manageabilityReport(new Set(['F_A', 'F_B']), [
            named('target', ['F_A']),
        ])
        expect(report.canAdminister).toBe(false)
        expect(report.manageable).toEqual([])
        expect(report.blocked).toEqual([])
    })

    it('combines the authorities of several roles — the union manages what neither role alone can', () => {
        const adminRole = named('admin', ['F_USER_ADD', 'F_A'])
        const extraRole = named('extra', ['F_B'])
        const target = named('target', ['F_A', 'F_B'])

        const fromAdminOnly = manageabilityReport(
            aggregateAuthorities([adminRole]),
            [target]
        )
        expect(fromAdminOnly.manageable).toEqual([])

        const fromBoth = manageabilityReport(
            aggregateAuthorities([adminRole, extraRole]),
            [target]
        )
        expect(fromBoth.manageable).toEqual([target])
    })

    it('explains each blocked role with the authorities it is missing', () => {
        const report = manageabilityReport(new Set(['F_USER_ADD']), [
            named('blocked', ['F_X', 'F_Y']),
        ])
        expect(report.manageable).toEqual([])
        expect(report.blocked).toEqual([
            { role: named('blocked', ['F_X', 'F_Y']), missing: ['F_X', 'F_Y'] },
        ])
    })

    it('flags a set limited to managed groups', () => {
        const limited = manageabilityReport(
            new Set(['F_USER_ADD_WITHIN_MANAGED_GROUP']),
            []
        )
        expect(limited.canAdminister).toBe(true)
        expect(limited.limitedToManagedGroups).toBe(true)

        const unlimited = manageabilityReport(
            new Set(['F_USER_ADD', 'F_USER_ADD_WITHIN_MANAGED_GROUP']),
            []
        )
        expect(unlimited.limitedToManagedGroups).toBe(false)
    })

    it('lets a superuser manage every role, including superuser roles', () => {
        const report = manageabilityReport(new Set([AUTHORITY_ALL]), [
            named('super', [AUTHORITY_ALL]),
            named('plain', ['F_A']),
        ])
        expect(report.blocked).toEqual([])
        expect(report.manageable).toHaveLength(2)
        expect(report.limitedToManagedGroups).toBe(false)
    })
})
