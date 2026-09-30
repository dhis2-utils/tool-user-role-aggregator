export interface UserRole {
    id: string
    displayName: string
    authorities?: string[]
}

export interface SystemAuthority {
    id: string
    name: string
}

/** The special authority that grants superuser access to everything */
export const AUTHORITY_ALL = 'ALL'
