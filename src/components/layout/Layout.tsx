import React from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from '../sidebar/Sidebar'
import styles from './Layout.module.css'

export const Layout = () => (
    <div className={styles.wrapper}>
        <Sidebar className={styles.sidebar} />
        <main className={styles.main}>
            <Outlet />
        </main>
    </div>
)
