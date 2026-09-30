import asyncio
import sys
from playwright.async_api import async_playwright

async def run(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        try:
            await page.click("text=O'Z", timeout=2000)
            await page.wait_for_timeout(1000)
        except: pass
        text = await page.evaluate("document.body.innerText")
        with open('etender_text.txt', 'w', encoding='utf-8') as f:
            f.write(text)
        await browser.close()

asyncio.run(run(sys.argv[1]))
