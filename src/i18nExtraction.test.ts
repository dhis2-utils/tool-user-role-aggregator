import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

// The DHIS2 translation extractor silently drops some i18n.t keys: keys with
// a colon and no nsSeparator, calls with a `count` option, and options with
// a TypeScript cast. A dropped key still renders in English but can never be
// translated. This test fails when a key in src/ is missing from
// i18n/en.pot, which `pnpm run build` regenerates.

const ROOT = path.resolve(__dirname, '..')
const SOURCE_FILE = /\.tsx?$/
const TEST_FILE = /\.test\.tsx?$/
const I18N_CALL = /i18n\.t\(\s*'((?:[^'\\]|\\.)*)'/g

const sourceFiles = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
            return entry.name === 'locales' ? [] : sourceFiles(full)
        }
        return SOURCE_FILE.test(entry.name) && !TEST_FILE.test(entry.name)
            ? [full]
            : []
    })

const keysInSource = (): Set<string> => {
    const keys = new Set<string>()
    for (const file of sourceFiles(path.join(ROOT, 'src'))) {
        for (const match of readFileSync(file, 'utf8').matchAll(I18N_CALL)) {
            keys.add(match[1].replace(/\\'/g, "'"))
        }
    }
    return keys
}

// A msgid is one or more quoted strings, joined.
const keysInPot = (): Set<string> => {
    const pot = readFileSync(path.join(ROOT, 'i18n', 'en.pot'), 'utf8')
    const keys = new Set<string>()
    for (const block of pot.split(/\n\n+/)) {
        const msgid = /msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)msgstr/.exec(block)
        if (msgid) {
            const parts = msgid[1].match(/"(?:[^"\\]|\\.)*"/g) ?? []
            keys.add(parts.map((part) => JSON.parse(part) as string).join(''))
        }
    }
    return keys
}

describe('i18n extraction', () => {
    it('has every i18n.t key from src/ in i18n/en.pot', () => {
        const pot = keysInPot()
        const missing = [...keysInSource()].filter((key) => !pot.has(key))
        expect(missing).toEqual([])
    })

    it('finds the keys it checks', () => {
        expect(keysInSource().size).toBeGreaterThan(20)
    })
})
