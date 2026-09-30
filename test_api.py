import asyncio
import sys
from playwright.async_api import async_playwright

async def run(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        page.on("response", lambda response: print(f"API: {response.url}") if "/api/" in response.url else None)
        
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await browser.close()

asyncio.run(run(sys.argv[1]))
