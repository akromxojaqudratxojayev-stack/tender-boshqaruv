import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # O'zbek tilida ochish uchun locale ni set qilamiz
        context = await browser.new_context(locale="uz-UZ")
        page = await context.new_page()
        await page.goto('https://etender.uzex.uz/lot/509118', wait_until='networkidle')
        
        # Til tugmasini bosib o'zbek tiliga o'tkazishni ham qilib ko'ramiz (agar bo'lsa)
        try:
            await page.click("text=O'Z", timeout=2000)
            await page.wait_for_timeout(1000)
        except:
            pass
            
        text = await page.evaluate('document.body.innerText')
        with open('page_text.txt', 'w', encoding='utf-8') as f:
            f.write(text)
        await browser.close()

asyncio.run(run())
