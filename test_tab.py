import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://xt-xarid.uz/procedure/8865311/core', wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        try:
            await page.locator("text=Шартнома намунаси").click(timeout=2000, force=True)
            print("Clicked tab!")
            await page.wait_for_timeout(2000)
        except Exception as e:
            print("Could not click tab:", e)
            
        html = await page.content()
        with open('tab_html.txt', 'w', encoding='utf-8') as f:
            f.write(html)
        m = re.findall(r'<label>[^<]*(?:Буюртмачи|Buyurtmachi)\s*:\s*</label>[^>]*<input[^>]+(?:title|value)="([^"]+)"', html, re.I)
        print("Company:", m)
        await browser.close()

asyncio.run(run())
