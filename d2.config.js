/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    name: 'tool-user-role-aggregator',
    title: 'User Admin Role Aggregator',
    description:
        'Tool to validate and create/modify user roles for users who should manage other users.',
    minDHIS2Version: '2.40',

    entryPoints: {
        app: './src/App.tsx',
    },

    viteConfigExtensions: './viteConfigExtensions.mts',
}

module.exports = config
