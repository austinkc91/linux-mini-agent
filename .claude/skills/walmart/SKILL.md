---
name: walmart
description: Walmart.com cart automation. Log into Walmart account, search for items, prefer frequently-bought products, and add to cart. Items sync to the Walmart mobile app.
---

# Walmart — Cart Automation Skill

Automate shopping on walmart.com using steer (GUI automation) and drive (terminal). This skill handles login, search, product selection with preference matching, and cart management.

## Prerequisites

- Chromium or Firefox browser available
- Walmart account credentials stored in `/home/austin/.walmart-credentials` (email on line 1, password on line 2)
- Frequently-bought preferences in `/home/austin/linux-mini-agent/.claude/skills/walmart/preferences.json`

## Workflow

### 1. Launch Browser & Navigate to Walmart

```bash
steer apps launch chromium --json
steer wait --app chromium --timeout 5 --json
steer see --app chromium --json
```

Navigate to walmart.com:
```bash
steer hotkey ctrl+l --json          # Focus address bar
steer type "https://www.walmart.com" --json
steer hotkey return --json
```

Wait for page to load, then verify with `steer see` or `steer ocr --store --json`.

### 2. Log Into Walmart Account

Check if already logged in by looking for "Account" or user name in the top nav.

If NOT logged in:
1. Click "Sign In" or the account icon in the top-right
2. Use `steer ocr --store --json` to find the sign-in elements
3. Enter email from credentials file
4. Click "Continue" / next step
5. Enter password from credentials file
6. Click "Sign In" button
7. Verify login succeeded by checking for the account name

**Important:** Walmart may show CAPTCHAs or verification prompts. If you encounter one, note it in your status update and try to work through it. If blocked, inform the user.

### 3. Search for Items & Select Preferred Products

For EACH item on the shopping list:

1. **Check preferences first** — Read `preferences.json` to see if there's a preferred product for this item category
2. **Search Walmart** — Click the search bar, type the preferred product name (or generic item name if no preference), and hit Enter
3. **Find the right product** — Use `steer ocr --store --json` to read search results. Look for the preferred brand/size from preferences. If the exact preferred product appears, select it. If not, pick the closest match.
4. **Add to cart** — Click "Add to cart" button on the product page
5. **Verify** — Confirm the item was added (look for cart count increase or "Added to cart" confirmation)
6. **Continue shopping** — Use the search bar for the next item (don't go to cart yet)

### 4. Verify Cart

After all items are added:
1. Click the cart icon
2. Use `steer ocr --store --json` to read cart contents
3. Verify all items are present
4. Report the cart summary (items, quantities, subtotal)

## Preference Matching Rules

The `preferences.json` file maps generic item names to specific products. When searching:

1. If a preference exists, search for the EXACT preferred product name (brand + size)
2. If the exact product isn't available, search for the same brand in a different size
3. If the brand isn't available at all, pick the most popular/best-rated alternative and note the substitution
4. For items with no preference, pick a well-reviewed mid-range option

## Tips

- Walmart.com is a standard website — use `steer ocr --store --json` for reading page content since accessibility trees may be incomplete
- After each page navigation, wait briefly and then OCR to read the new content
- The search bar is always at the top of the page
- "Add to cart" buttons are typically blue on Walmart
- If a popup or overlay appears (like a location prompt), dismiss it before continuing
- Scroll down if the product or "Add to cart" button isn't visible
- Cart syncs automatically to the Walmart mobile app once logged in

## Critical Safety Rules

- **NEVER place orders** — Only add items to cart. NEVER click "Check out", "Place order", or any purchase/payment buttons. The user will review and place the order themselves.
- NEVER log credentials in status updates or summaries
- NEVER include credentials in any output
- Read credentials only when needed for login, then discard from context
- If credentials file doesn't exist, ask the user to create it
