import { CssReset, CssVariables } from '@dhis2/ui'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { createHashRouter, Outlet, RouterProvider } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { RequireAuthority } from '@/components/RequireAuthority'
import {
    AUTHORITY_USER_VIEW,
    USERROLE_ADD_AUTHORITIES,
} from '@/domain/userRole'
import { CheckRolesPage } from '@/pages/CheckRolesPage'
import { CheckUserPage } from '@/pages/CheckUserPage'
import { CreateRolePage } from '@/pages/CreateRolePage'
import { UpdateRolePage } from '@/pages/UpdateRolePage'
import { SyncUrlWithGlobalShell } from '@/utils/SyncUrlWithGlobalShell'

const queryClient = new QueryClient()

const router = createHashRouter([
    {
        element: <SyncUrlWithGlobalShell />,
        children: [
            {
                element: <Layout />,
                children: [
                    {
                        element: (
                            <PageWrapper>
                                <Outlet />
                            </PageWrapper>
                        ),
                        children: [
                            { path: '/', element: <CheckRolesPage /> },
                            {
                                path: '/check-user',
                                element: (
                                    <RequireAuthority
                                        anyOf={[AUTHORITY_USER_VIEW]}
                                    >
                                        <CheckUserPage />
                                    </RequireAuthority>
                                ),
                            },
                            {
                                path: '/create',
                                element: (
                                    <RequireAuthority
                                        anyOf={USERROLE_ADD_AUTHORITIES}
                                    >
                                        <CreateRolePage />
                                    </RequireAuthority>
                                ),
                            },
                            {
                                path: '/update',
                                element: (
                                    <RequireAuthority
                                        anyOf={USERROLE_ADD_AUTHORITIES}
                                    >
                                        <UpdateRolePage />
                                    </RequireAuthority>
                                ),
                            },
                        ],
                    },
                ],
            },
        ],
    },
])

const App = () => (
    <QueryClientProvider client={queryClient}>
        <CssReset />
        <CssVariables theme spacers colors elevations />
        <RouterProvider router={router} />
    </QueryClientProvider>
)

export default App
