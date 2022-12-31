/*
Visual tests for 20kbps_pyramid
  - Take a screenshot from the legacy site and from the development site.
  - Compare the screenshots using ImageMagick compare.

Development site must be running without debug toolbar:

```shell
pserve development_nodebugtoolbar.ini
```

`compare` is assumed to be available as a shell command and is executed using node:child_process.exec.

The compare metric is currently AE (Absolute Error) without fuzz, so the pages must be a pixel-perfect match.
*/
const fsPromises = require('fs').promises
const util = require('util')
const exec = util.promisify(require('child_process').exec)


const VIEWPORT_WIDTH = 540
const VIEWPORT_HEIGHT = 22000

const DEV_SITE_BASE = 'http://127.0.0.1:6543'
const LEGACY_SITE_BASE = 'https://20kbps.net'


function timeout(ms) {
    if (!ms) return
    return new Promise((resolve) => { setTimeout(() => { resolve() }, ms)})
}


const compareCommand = (fileStem) => `compare -metric AE ${fileStem}__legacy.png ${fileStem}__dev.png null:`


async function comparePages(path, afterNetworkIdleTimeout) {
    const fileStem = path.replace('/', '_')

    await page.goto(`${DEV_SITE_BASE}/${path}`, {waitUntil: 'networkidle0'})
    await timeout(afterNetworkIdleTimeout)
    await page.screenshot({path: `${fileStem}__dev.png`})

    await page.goto(`${LEGACY_SITE_BASE}/${path}`, {waitUntil: 'networkidle0'})
    await timeout(afterNetworkIdleTimeout)
    await page.screenshot({path: `${fileStem}__legacy.png`})

    const { stderr } = await exec(compareCommand(fileStem))
    expect(stderr).toBe('0')
}


beforeEach(async () => {
    await page.setViewport({width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT})
})


afterEach(async () => {
    const screenshots = (await fsPromises.readdir('.')).filter((f) => f.endsWith('__dev.png') || f.endsWith('__legacy.png'))
    await Promise.all(screenshots.map((f) => fsPromises.unlink(f)))
})


test('compare index2.htm', async () => {
    await comparePages('index2.htm')
})
