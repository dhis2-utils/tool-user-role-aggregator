import path from 'node:path'
import type { ConfigEnv } from 'vite'
import { defineConfig } from 'vite'

const viteConfig = defineConfig((configEnv: ConfigEnv) => {
    const { mode } = configEnv
    return {
        // In dev environments, don't clear the terminal after files update
        clearScreen: mode !== 'development',
        // Use an import alias: import from '@/' anywhere instead of 'src/'
        resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
        // ...other config options here
    }
})

export default viteConfig
