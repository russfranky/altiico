from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()

    # Verify Home Page
    page.goto("http://localhost:5173/")
    page.wait_for_timeout(2000) # Wait for 3D scene or anything to settle
    page.screenshot(path="verification_home.png", full_page=True)
    print("Home page screenshot taken.")

    # Verify Avatars Page
    page.goto("http://localhost:5173/avatars")
    page.wait_for_timeout(1000)
    page.screenshot(path="verification_avatars.png", full_page=True)
    print("Avatars page screenshot taken.")

    # Verify Collections Page
    page.goto("http://localhost:5173/collections")
    page.wait_for_timeout(1000)
    page.screenshot(path="verification_collections.png", full_page=True)
    print("Collections page screenshot taken.")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
