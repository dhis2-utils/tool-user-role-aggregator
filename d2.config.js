/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    name: 'tool-user-role-aggregator',
    title: 'User Admin Role Aggregator',
    description:
        'Checks which user roles a user administrator can manage, and creates or extends roles for user administrators.',
    minDHIS2Version: '2.40',

    entryPoints: {
        app: './src/App.tsx',
    },

    viteConfigExtensions: './viteConfigExtensions.mts',
}

module.exports = config
