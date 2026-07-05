# STR Financial System — User Guide

**Version 1.0 | For Airbnb, Vrbo & Vacation Rental Hosts**

> ⚠️ **Disclaimer:** This spreadsheet is an organizational tool only. It does **not** constitute tax, legal, or financial advice. Always consult a licensed CPA or tax professional before filing your tax return.

---

## What's Included

| Tab | What it does |
|-----|-------------|
| 🏡 **Setup** | Configure your properties and platform commission rates |
| 📅 **Bookings** | Log every reservation; platform fees and payout calculated automatically |
| 💳 **Expenses** | Track every expense, pre-organized by IRS Schedule E category |
| 📊 **Dashboard** | Live KPIs: ADR, Occupancy Rate, RevPAR, Net Profit |
| 📈 **P&L** | Full Profit & Loss breakdown by property |
| 🧾 **Tax Summary** | Totals grouped by Schedule E line — share directly with your CPA |
| 🧹 **Cleaning** | Log every turnover: cleaner, cost, duration, status |
| 📦 **Supplies** | Inventory tracker with low-stock alerts |

---

## Quick Start (5 minutes)

### Step 1 — Make a copy

> **File → Make a copy** in Google Drive. Work only on your copy; never edit the original template.

### Step 2 — Setup tab

1. Open the **🏡 Setup** tab.
2. In **STEP 1**, replace the example property names with yours (up to 5 properties).
3. In **STEP 2**, verify the commission percentages match your current platform agreements.
   - Airbnb default: **3%** (host fee, standard)
   - Vrbo default: **5%**
   - Booking.com default: **15%**
   - Direct bookings: **0%**

> 💡 These rates feed every automatic calculation in Bookings, Dashboard, and P&L. Get them right once and you're done.

### Step 3 — Log your first booking (Bookings tab)

1. Open **📅 Bookings**.
2. Enter Check-In and Check-Out dates in columns A and B → Nights (column C) calculates automatically.
3. Select your **Property** and **Platform** from the dropdowns.
4. Enter **Gross amount** (what the guest paid, before platform fees).
5. **Platform Fee** and **Payout Net** calculate automatically — no formulas to touch.

> ✅ Every booking you log instantly updates the Dashboard, P&L, and Tax Summary.

### Step 4 — Log your expenses (Expenses tab)

1. Open **💳 Expenses**.
2. Enter the date, select Property (or "ALL" for portfolio-wide expenses like insurance), and pick a **Category** from the dropdown.
   - Categories are pre-mapped to IRS Schedule E lines — this is what saves you time at tax season.
3. Enter the Amount and Vendor.

### Step 5 — Read your Dashboard (weekly habit)

Open **📊 Dashboard** and check your 6 core KPIs:

| KPI | What it means |
|-----|--------------|
| **ADR** (Avg Daily Rate) | Revenue per *booked* night |
| **Occupancy %** | Booked nights ÷ available nights (edit "90" in the formula to match your actual available days) |
| **RevPAR** | ADR × Occupancy — your true revenue efficiency metric |
| **Total Payout** | Net cash received across all properties |
| **Total Expenses** | All logged expenses |
| **Net Profit** | Payout minus expenses |

> 💡 **Industry benchmark (2026):** RevPAR target ~$119.90. ADR goal: $150+. Occupancy: aim for ≥ 50% to maintain Superhost status.

---

## Tax Season (Tax Summary tab)

1. Open **🧾 Tax Summary** at the end of each tax year.
2. Every expense is automatically grouped by the correct **Schedule E line** (L5 through L19).
3. **Share this tab** (or export as PDF) with your CPA — no manual totaling needed.

> ⚠️ **Important:** The "2026" year in column D is editable. Update it annually. This spreadsheet covers one tax year at a time; duplicate the file for each year.

---

## Tips & Best Practices

**Cleaning & Supplies tracking**

- Use **🧹 Cleaning** to log every turnover: date, cleaner name, cost, and duration. Helps you audit costs and plan ahead.
- Use **📦 Supplies** to track par levels. Items marked **"Order Now"** are highlighted in red — restock before your next check-in.

**Multiple properties**

- The property dropdown ("Property 1" through "Property 5") feeds every formula in every tab.
- Want custom names? Change them in **Setup → STEP 1**, then update any dropdown references that use the exact text. *(Note: changing property names requires updating dropdown lists manually — a future version will handle this automatically.)*

**Occupancy % formula**

The Occupancy formula in Dashboard uses **90 nights** as the denominator (≈ one quarter). To match your real available calendar:
- Edit the formula in column E of the Dashboard property table: change `90` to your actual available nights (e.g., `365` for annual, `30` for monthly).

**Adding more rows**

- Bookings: rows 3–100 are pre-formatted. For more than 98 bookings, copy the last formatted row and paste downward — formulas will extend.
- Expenses: same pattern, rows 3–100.

---

## Frequently Asked Questions

**Q: Can I add a 6th property?**
A: Not in this version. The system is architected for 1–5 properties. A "10-Property Edition" is available — contact the seller.

**Q: Does this work with Excel?**
A: It's built for **Google Sheets** only. Some formulas (ARRAYFORMULA, VLOOKUP with sheet references) may not translate cleanly to Excel.

**Q: Can I change the currency?**
A: Yes. Select the columns with $ format → Format → Number → Custom currency, and choose your local currency. Note: Tax Summary references US Schedule E — for non-US users, the tax section is a template you can relabel for your local tax form.

**Q: What about depreciation?**
A: Depreciation (Schedule E L19/20) is not auto-calculated — it requires appraisal data and CPA input. Add a manual row in Tax Summary for your CPA to complete.

**Q: How do I handle shared expenses (e.g., one insurance policy for all properties)?**
A: Log them with **Property = ALL**. The P&L tab distributes ALL-tagged expenses equally across properties in its summary view.

---

## Disclaimer (full)

This spreadsheet template is provided for **organizational and record-keeping purposes only**. It does not constitute tax, legal, accounting, or financial advice. The Schedule E categories and references are provided as a general guide based on commonly applicable US tax rules for short-term rental income. Tax laws change and vary by individual situation. **Always consult a licensed CPA or tax professional** before preparing or filing your tax return. The seller assumes no liability for tax filings made based on this tool.

*Not affiliated with or endorsed by Airbnb, Vrbo, Booking.com, or any listed platform.*

---

*STR Financial System v1.0 — For Airbnb, Vrbo & Vacation Rental Hosts*
*Questions or feedback? Contact the seller through Etsy.*
