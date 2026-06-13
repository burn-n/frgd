import asyncio
import os
import aiohttp
from playwright.async_api import async_playwright

BASE_URL = "https://guns.lol/{}"
RATE_RETRY_DELAY = 120

# -------- ENV VARIABLES -------- #
WEBHOOK_AVAILABLE = os.getenv("WEBHOOK_AVAILABLE") or "https://discord.com/api/webhooks/1487940802138210304/CB5y4Y-ulRvMxZrrEw_m8VIVHnXVI6kEzoxphkJDQjs4PLwoh0gnv0NlioF20Y6LW-jS"
WEBHOOK_TAKEN = os.getenv("WEBHOOK_TAKEN") or "https://discord.com/api/webhooks/1488700392798818414/btjVtlIHeGCi44G38WcTNuEQXvqcnNI59AhRFLn4ZZnZPam3xZxf6ko39ajWQpJgrJ7k"
WEBHOOK_BANNED = os.getenv("WEBHOOK_BANNED") or "https://discord.com/api/webhooks/1488700445047263254/tzMhXlW-thXQ2SL2WvV8sC3gHBgI-4gvKMgISccACHzbOEHz62iXnHKK4VVQohlac9ll"
WEBHOOK_RATE = os.getenv("WEBHOOK_RATE") or "https://discord.com/api/webhooks/1488700500877774958/_SJCUAGgIi_TkCpXp9VJCAFC3QM9Qo7UqtIKhjLu5ENZBd7ZRnw5bCTUhm-hT54pgjP8"

CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "10"))  # seconds between checks
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Global last status for change detection
last_status = None

# -------- WEBHOOK -------- #
async def send_live(webhook, session, msg, allow_mentions=False):
    if not webhook:
        return
    payload = {
        "content": msg,
        "allowed_mentions": (
            {"parse": ["everyone", "roles"]} if allow_mentions else {"parse": []}
        )
    }
    async with session.post(webhook, json=payload) as resp:
        if resp.status == 429:
            retry = float(resp.headers.get("Retry-After", "1"))
            await asyncio.sleep(retry)
        elif resp.status >= 400:
            text = await resp.text()
            print(f"[WEBHOOK ERROR {resp.status}] {text}")


# -------- CHECK USERNAME -------- #
async def check_username(page, username, session):
    global last_status
    try:
        await page.goto(
            BASE_URL.format(username),
            timeout=20000,
            wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(300)

        # Rate limit check
        body_text = (await page.inner_text("body")).lower()
        if "too many requests" in body_text:
            await send_live(
                WEBHOOK_RATE,
                session,
                f"⏳ RATE LIMITED on guns.lol — sleeping {RATE_RETRY_DELAY}s"
            )
            await asyncio.sleep(RATE_RETRY_DELAY)
            return "rate_limited"

        # Get status from H1
        try:
            h1_text = (await page.locator("h1").first.inner_text()).strip().lower()
        except:
            h1_text = ""

        if h1_text == "username not found":
            status = "available"
        elif h1_text == "this user has been banned":
            status = "banned"
        else:
            status = "taken"

        # Notify only on status change
        if status != last_status and last_status is not None:
            if status == "available":
                await send_live(
                    WEBHOOK_AVAILABLE,
                    session,
                    f"✅ **AVAILABLE**: `r` <@&1466285392717414400>",
                    allow_mentions=True
                )
            elif status == "banned":
                await send_live(
                    WEBHOOK_BANNED,
                    session,
                    f"⚠️ **BANNED**: `r` <@&1465095383259549818>",
                    allow_mentions=True
                )
            elif status == "taken":
                await send_live(
                    WEBHOOK_TAKEN,
                    session,
                    f"❌ `r` is now taken"
                )

        if last_status != status:
            print(f"[{asyncio.get_event_loop().time():.0f}] Status changed → {status.upper()}")

        last_status = status
        return status

    except Exception as e:
        print(f"Error checking 'r': {e}")
        return "error"


# -------- MAIN MONITOR -------- #
async def main():
    print("🚀 Starting monitor for https://guns.lol/r")
    print(f"Check interval: {CHECK_INTERVAL} seconds\n")

    async with aiohttp.ClientSession() as session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            page = await browser.new_page(user_agent=USER_AGENT)
            
            try:
                while True:
                    await check_username(page, "r", session)
                    await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                print("Monitor stopped.")
            except KeyboardInterrupt:
                print("Stopped by user.")
            finally:
                await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
