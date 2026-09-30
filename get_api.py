import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        data = {}
        
        async def handle_response(response):
            if "api" in response.url and response.request.resource_type == "fetch":
                try:
                    js = await response.json()
                    data[response.url] = js
                except:
                    pass
                    
        page.on("response", handle_response)
        
        await page.goto('https://xt-xarid.uz/procedure/8830175/core', wait_until='networkidle')
        await page.wait_for_timeout(5000)
        
        with open('xt_api.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        await browser.close()

asyncio.run(run())
