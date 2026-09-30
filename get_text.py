import asyncio
from playwright.async_api import async_playwright

async def run():
    p = await async_playwright().start()
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto('https://xt-xarid.uz/procedure/8830175/core', wait_until='networkidle')
    await page.wait_for_timeout(5000)
    text = await page.evaluate('document.body.innerText')
    with open('xt_text_waited.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    await browser.close()
    await p.stop()

asyncio.run(run())
