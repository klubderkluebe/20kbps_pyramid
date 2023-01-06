/*
Visual tests for 20kbps_pyramid
  - Take a screenshot from the legacy site and from the development site.
  - Compare the screenshots using ImageMagick compare.

Development site must be running without debug toolbar:

```shell
pserve development_nodebugtoolbar.ini
```

`compare` is assumed to be available as a shell command and is executed using node:child_process.exec.

The compare metric is currently AE (Absolute Error) without fuzz.
A single test case passes when less than {TOLERANCE_PERCENTAGE} percent of pixels differ between legacy and dev.
*/
const fsPromises = require('fs').promises
const util = require('util')
const exec = util.promisify(require('child_process').exec)

const releaseDirs = require('./releaseDirs')

const log = require('console').error

const PAGE_LOAD_TIMEOUT = 7000
const TOLERANCE_PERCENTAGE = 0.01

const DEFAULT_VIEWPORT_WIDTH = 1000
const DEFAULT_VIEWPORT_HEIGHT = 5000

const DEV_SITE_BASE = 'http://127.0.0.1:6543'
const LEGACY_SITE_BASE = 'https://20kbps.net'


function timeout(ms) {
    if (!ms) return
    return new Promise((resolve) => { setTimeout(() => { resolve() }, ms)})
}


// const compareCommand = (fileStem) => `compare -metric AE ${fileStem}__legacy.png ${fileStem}__dev.png null:`
const compareCommand = (fileStem) => `compare -metric AE ${fileStem}__legacy.png ${fileStem}__dev.png ${fileStem}__diff.png`


async function pageGotoIgnoreTimeout(url) {
    try {
        await page.goto(url, {
            waitUntil: 'load',
            timeout: PAGE_LOAD_TIMEOUT,
        })
    } catch (err) {
        if (err.name !== 'TimeoutError')
            throw err
    }
}


async function comparePages(path, afterNetworkIdleTimeout, viewportWidth, viewportHeight) {
    function removePlayers() {
        const audioElements = document.querySelectorAll('audio')
        for (let elem of audioElements) {
            elem.parentNode.removeChild(elem)
        }
        const iframe = document.querySelector('iframe')
        if (iframe) {
            iframe.parentNode.removeChild(iframe)
        }
    }

    log(path)

    const fileStem = path.replaceAll('/', '_')
    const width = viewportWidth || DEFAULT_VIEWPORT_WIDTH
    const height = viewportHeight || DEFAULT_VIEWPORT_HEIGHT

    await page.setViewport({width, height})
    await page.setCacheEnabled(false)

    const sanitizedPath =
        (path === 'index2.htm' || path.slice(-1) === '/')
        ? path
        : path + '/'

    await pageGotoIgnoreTimeout(`${DEV_SITE_BASE}/${sanitizedPath}`)
    await page.evaluate(removePlayers)
    await timeout(afterNetworkIdleTimeout)
    await page.screenshot({path: `${fileStem}__dev.png`})

    await pageGotoIgnoreTimeout(`${LEGACY_SITE_BASE}/${sanitizedPath}`)
    await page.evaluate(removePlayers)
    await timeout(afterNetworkIdleTimeout)
    await page.screenshot({path: `${fileStem}__legacy.png`})

    let stderr
    try {
        stderr = (await exec(compareCommand(fileStem))).stderr
    } catch (err) {
        stderr = err.stderr
    }
    const errorPct = 100 * Number(stderr) / (width * height)
    expect(errorPct).toBeLessThan(TOLERANCE_PERCENTAGE)
}


test('compare index2.htm', async () => {
    await comparePages('index2.htm', 1200, 540, 22000)
})


for (let releaseDir of releaseDirs) {
    test(`compare ${releaseDir}`, async () => {
        await comparePages(`Releases/${releaseDir}`)
    })    
}

