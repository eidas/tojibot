import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError

SCREENSHOT_DIR = Path("/tmp/tojibot/screenshots")

PAGE_LOAD_TIMEOUT = 30_000
LOGIN_TIMEOUT = 30_000
IMAGE_UPLOAD_TIMEOUT = 15_000
POST_TIMEOUT = 30_000


class XPoster:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def post(self, text: str, image_paths: list[Path]) -> bool:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                return await self._do_post(page, text, image_paths)
            except Exception:
                await self._save_screenshot(page, "error")
                raise
            finally:
                await browser.close()

    async def _do_post(self, page: Page, text: str, image_paths: list[Path]) -> bool:
        await page.goto("https://x.com", timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded")

        state = await self._detect_page_state(page)

        if state == "login":
            await self._login(page)
        elif state == "home":
            pass
        else:
            await self._save_screenshot(page, "unknown_state")
            raise RuntimeError("Unknown page state after navigating to x.com")

        await self._compose_post(page, text, image_paths)
        return True

    async def _detect_page_state(self, page: Page) -> str:
        try:
            await page.wait_for_selector(
                'input[name="text"], input[autocomplete="username"]',
                timeout=5_000,
            )
            return "login"
        except PlaywrightTimeoutError:
            pass

        try:
            await page.wait_for_selector(
                '[data-testid="tweetButtonInline"], [data-testid="SideNav_NewTweet_Button"], [data-testid="primaryColumn"]',
                timeout=5_000,
            )
            return "home"
        except PlaywrightTimeoutError:
            pass

        return "unknown"

    async def _login(self, page: Page) -> None:
        username_input = page.locator('input[name="text"], input[autocomplete="username"]').first
        await username_input.fill(self._username)

        next_button = page.locator('div[role="button"]:has-text("Next"), div[role="button"]:has-text("次へ")').first
        await next_button.click()

        password_input = page.locator('input[name="password"]')
        await password_input.wait_for(timeout=LOGIN_TIMEOUT)
        await password_input.fill(self._password)

        login_button = page.locator('div[role="button"]:has-text("Log in"), div[role="button"]:has-text("ログイン")').first
        await login_button.click()

        await page.wait_for_selector(
            '[data-testid="tweetButtonInline"], [data-testid="SideNav_NewTweet_Button"], [data-testid="primaryColumn"]',
            timeout=LOGIN_TIMEOUT,
        )

    async def _compose_post(self, page: Page, text: str, image_paths: list[Path]) -> None:
        compose_button = page.locator(
            '[data-testid="SideNav_NewTweet_Button"], a[href="/compose/post"]'
        ).first
        try:
            await compose_button.click(timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        tweet_box = page.locator('[data-testid="tweetTextarea_0"], div[contenteditable="true"]').first
        await tweet_box.wait_for(timeout=PAGE_LOAD_TIMEOUT)
        await tweet_box.click()
        await tweet_box.fill(text)

        for img_path in image_paths:
            file_input = page.locator('input[data-testid="fileInput"], input[accept*="image"][type="file"]').first
            await file_input.set_input_files(str(img_path))

            await page.wait_for_selector('[data-testid="attachments"]', timeout=IMAGE_UPLOAD_TIMEOUT)
            await asyncio.sleep(5)

        post_button = page.locator(
            '[data-testid="tweetButtonInline"], [data-testid="tweetButton"]'
        ).first
        await post_button.click(timeout=POST_TIMEOUT)

        try:
            await page.wait_for_selector(
                '[data-testid="toast"], [data-testid="tweetTextarea_0"]:not([class*="notEmpty"])',
                timeout=POST_TIMEOUT,
            )
        except PlaywrightTimeoutError:
            await self._save_screenshot(page, "post_confirm_timeout")
            raise RuntimeError("Timed out waiting for post confirmation")

    async def _save_screenshot(self, page: Page, label: str) -> None:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"{label}_{ts}.png"
        try:
            await page.screenshot(path=str(path))
        except Exception:
            pass
