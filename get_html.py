import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://xt-xarid.uz/procedure/8865682/core', wait_until='networkidle')
        await page.wait_for_timeout(3000) # extra wait
        html = await page.content()
        with open('xt_html.txt', 'w', encoding='utf-8') as f:
            f.write(html)
        await browser.close()

asyncio.run(run())
