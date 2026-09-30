import asyncio
from playwright.async_api import async_playwright

async def run(url, filename):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="uz-UZ")
        page = await context.new_page()
        print(f"Loading {url}...")
        await page.goto(url, wait_until="networkidle")
        
        # O'zbek tiliga o'tkazishga urinib ko'ramiz
        try:
            await page.click("text=O'Z", timeout=2000)
            await page.wait_for_timeout(1000)
        except:
            pass
            
        try:
            await page.click("text=O'ZBEKCHA", timeout=2000)
            await page.wait_for_timeout(1000)
        except:
            pass
            
        text = await page.evaluate('document.body.innerText')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Saved to {filename}")
        await browser.close()

async def main():
    await run("https://xt-xarid.uz/procedure/8830175/core", "xt_xarid.txt")
    await run("https://xarid.uzex.uz/shop/lot-details/5605318", "xarid_uzex.txt")

asyncio.run(main())
