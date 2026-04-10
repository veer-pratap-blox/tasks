# Favorable Direction Heuristic Pattern Table

This document captures the complete pattern table used by `favorable_direction.py`, including:

- Nonsense / early-exit rules
- Decrease patterns
- Increase patterns
- Default behavior when no pattern matches

## Matching logic

The heuristic matches against the normalized indicator name using:

`re.search(pattern, name.lower().strip())`

### Notes

- Matching is done against the full lowercased, trimmed name.
- A pattern can match anywhere in the string unless it uses anchors like `^` or `$`.
- `\b` means a word boundary, so it typically matches whole words separated by spaces or punctuation.
- Nonsense / early-exit rules are evaluated first and force the result to `increase` before the decrease/increase keyword lists are checked.

---

## A. Nonsense / early rules -> `increase`

| # | Pattern | Example names that match |
|---|---|---|
| A1 | `^[_\-\s\.]+$` | `---`, `___`, `   `, `...` |
| A2 | `^\d+$` | `0`, `42`, `2024` |
| A3 | `^[a-z]{1,2}\d*$` | `a`, `ab`, `a1`, `z9` |
| A4 | `^(test|calc|check|data|input|raw|indicator|ind|block|demo|example|dummy|temp|misc|ref|flow)` | `test revenue`, `demo KPI`, `input 1`, `block total`, `temp metric` |
| A5 | `workings` | `P&L workings`, `Model workings`, `---- Workings ----` |
| A6 | `^---+$` | `---`, `-----` |

---

## B. Decrease patterns

| # | Pattern | Example names that match |
|---|---|---|
| D1 | `\bcost(s)?\b` | `Total cost`, `Total costs`, `Unit cost`, `Fixed costs` |
| D2 | `\bexpens(e|es|iture)\b` | `Operating expense`, `Operating expenses`, `Operating expenditure`, `Travel expense`, `Other expenses` |
| D3 | `\bspend(ing)?\b` | `Marketing spend`, `Marketing spending`, `Ad spend`, `Cloud spending` |
| D4 | `\boverhead(s)?\b` | `Overhead`, `Overheads`, `Factory overhead` |
| D5 | `\bopex\b` | `Opex`, `Group opex`, `Opex - HQ` |
| D6 | `\bcogs?\b` | `COGS`, `Cog`, `COG` |
| D7 | `\bcost of (sales|goods|revenue|service)\b` | `Cost of sales`, `Cost of goods`, `Cost of revenue`, `Cost of service` |
| D8 | `\bdirect costs?\b` | `Direct cost`, `Direct costs` |
| D9 | `\bindirect costs?\b` | `Indirect cost`, `Indirect costs` |
| D10 | `\bloss(es)?\b` | `Loss`, `Losses`, `Trading loss`, `FX losses` |
| D11 | `\bwrite.?off\b` | `Write off`, `Write-off`, `Write.off`, `Asset write off` |
| D12 | `\bimpairment\b` | `Impairment`, `Goodwill impairment` |
| D13 | `\bbad debt\b` | `Bad debt`, `Bad debt expense` |
| D14 | `\bchurn\b` | `Churn`, `Monthly churn`, `Logo churn` |
| D15 | `\battrition\b` | `Attrition`, `Staff attrition` |
| D16 | `\bcancell` | `Cancellation`, `Cancelled`, `Cancellations`, `Cancel rate` |
| D17 | `\bdebt\b` | `Debt`, `Net debt`, `Total debt` |
| D18 | `\bliabilit(y|ies)\b` | `Liability`, `Liabilities`, `Current liabilities` |
| D19 | `\bloan(s)?\b` | `Loan`, `Loans`, `Bank loans` |
| D20 | `\bborrowin` | `Borrowing`, `Borrowings` |
| D21 | `\binterest expense\b` | `Interest expense`, `Bank interest expense` |
| D22 | `\binterest paid\b` | `Interest paid`, `Cash interest paid` |
| D23 | `\baccounts payable\b` | `Accounts payable`, `Trade accounts payable` |
| D24 | `\bpayable(s)?\b` | `Payable`, `Payables`, `Trade payables` |
| D25 | `\bcreditor(s)?\b` | `Creditor`, `Creditors`, `Trade creditors` |
| D26 | `\baccrual(s)?\b` | `Accrual`, `Accruals`, `Month-end accruals` |
| D27 | `\bdeferred (income|revenue)\b` | `Deferred income`, `Deferred revenue` |
| D28 | `\bdepreciation\b` | `Depreciation`, `PPE depreciation` |
| D29 | `\bamortisation\b` | `Amortisation`, `Software amortisation` |
| D30 | `\bamortization\b` | `Amortization`, `Intangible amortization` |
| D31 | `\btax(es)?\b` | `Tax`, `Taxes`, `Other taxes` |
| D32 | `\bcorporation tax\b` | `Corporation tax`, `UK corporation tax` |
| D33 | `\bincome tax\b` | `Income tax`, `Income tax expense` |
| D34 | `\bvat\b` | `VAT`, `VAT payable` |
| D35 | `\bgst\b` | `GST`, `GST paid` |
| D36 | `\bsalar(y|ies)\b` | `Salary`, `Salaries`, `Base salary` |
| D37 | `\bwage(s)?\b` | `Wage`, `Wages`, `Hourly wages` |
| D38 | `\bpayroll\b` | `Payroll`, `Monthly payroll` |
| D39 | `\bbonus(es)?\b` | `Bonus`, `Bonuses`, `Sales bonus` |
| D40 | `\bbenefits\b` | `Benefits`, `Employee benefits` |
| D41 | `\brent\b` | `Rent`, `Office rent` |
| D42 | `\binsurance\b` | `Insurance`, `D&O insurance` |
| D43 | `\bmaintenance\b` | `Maintenance`, `Building maintenance` |
| D44 | `\brepair(s)?\b` | `Repair`, `Repairs`, `Equipment repairs` |
| D45 | `\bfreight\b` | `Freight`, `Inbound freight` |
| D46 | `\bshipping\b` | `Shipping`, `Shipping costs label` |
| D47 | `\bdelivery cost\b` | `Delivery cost`, `Last mile delivery cost` |
| D48 | `\blegal fees?\b` | `Legal fee`, `Legal fees` |
| D49 | `\baccountan(cy|t) fees?\b` | `Accountancy fees`, `Accountant fees` |
| D50 | `\baudit\b` | `Audit`, `Audit fees` |
| D51 | `\bmarketing cost(s)?\b` | `Marketing cost`, `Marketing costs` |
| D52 | `\bmarketing spend\b` | `Marketing spend` |
| D53 | `\badvertising (cost|spend|expense)` | `Advertising cost`, `Advertising spend`, `Advertising expense` |
| D54 | `\bcac\b` | `CAC`, `Blended CAC` |
| D55 | `\bcustomer acquisition cost\b` | `Customer acquisition cost` |
| D56 | `\binfrastructure cost\b` | `Infrastructure cost` |
| D57 | `\bhosting cost\b` | `Hosting cost` |
| D58 | `\bcloud cost\b` | `Cloud cost` |
| D59 | `\bcompute cost\b` | `Compute cost` |
| D60 | `\bapi cost\b` | `API cost` |
| D61 | `\bburn rate\b` | `Burn rate`, `Net burn rate` |
| D62 | `\bcash burn\b` | `Cash burn`, `Monthly cash burn` |
| D63 | `\bdiscount(s)?\b` | `Discount`, `Discounts`, `Sales discounts` |
| D64 | `\brefund(s)?\b` | `Refund`, `Refunds` |
| D65 | `\breturn(s)?\b` | `Return`, `Returns`, `Product returns` |
| D66 | `\bacquisition cost\b` | `Acquisition cost` |
| D67 | `\bacquisition spend\b` | `Acquisition spend` |
| D68 | `\bdays payable\b` | `Days payable` |
| D69 | `\bdpo\b` | `DPO`, `Trade DPO` |
| D70 | `\butilities\b` | `Utilities`, `Office utilities` |
| D71 | `\belectricit(y|ies)\b` | `Electricity`, `Electricities` |
| D72 | `\bfuel cost\b` | `Fuel cost` |
| D73 | `\btravel (cost|expense)\b` | `Travel cost`, `Travel expense` |
| D74 | `\boffice expense\b` | `Office expense` |
| D75 | `\bbank (charge|fee)\b` | `Bank charge`, `Bank fee` |
| D76 | `\braw material cost\b` | `Raw material cost` |
| D77 | `\bdirect material cost\b` | `Direct material cost` |
| D78 | `\blabou?r cost\b` | `Labour cost`, `Labor cost` |
| D79 | `\bprovision\b` | `Provision`, `Bad debt provision` |
| D80 | `\bdividend(s)?\b` | `Dividend`, `Dividends` |
| D81 | `\blost (revenue|customers|business)\b` | `Lost revenue`, `Lost customers`, `Lost business` |
| D82 | `\bleavers?\b` | `Leaver`, `Leavers` |

---

## C. Increase patterns

| # | Pattern | Example names that match |
|---|---|---|
| I1 | `\brevenue\b` | `Revenue`, `Total revenue`, `Net revenue` |
| I2 | `\bsales\b` | `Sales`, `Net sales`, `Product sales` |
| I3 | `\bincome\b` | `Income`, `Other income`, `Rental income` |
| I4 | `\bprofit\b` | `Profit`, `Operating profit` |
| I5 | `\bgross (profit|margin)\b` | `Gross profit`, `Gross margin` |
| I6 | `\bnet (profit|income|margin)\b` | `Net profit`, `Net income`, `Net margin` |
| I7 | `\bebitda\b` | `EBITDA`, `Adjusted EBITDA` |
| I8 | `\bebit\b` | `EBIT`, `Reported EBIT` |
| I9 | `\bmargin\b` | `Margin`, `Contribution margin` |
| I10 | `\bgrowth\b` | `Growth`, `Revenue growth` |
| I11 | `\bcustomer(s)?\b` | `Customer`, `Customers`, `Active customer` |
| I12 | `\bactive (customers|users|members|agents|subscriptions)\b` | `Active customers`, `Active users`, `Active members`, `Active agents`, `Active subscriptions` |
| I13 | `\bnew customers?\b` | `New customer`, `New customers` |
| I14 | `\bsignups?\b` | `Signup`, `Signups` |
| I15 | `\bconversion\b` | `Conversion`, `Trial conversion` |
| I16 | `\bmrr\b` | `MRR`, `Group MRR` |
| I17 | `\barr\b` | `ARR`, `Logo ARR` |
| I18 | `\bacv\b` | `ACV`, `New ACV` |
| I19 | `\brecurring revenue\b` | `Recurring revenue` |
| I20 | `\bsubscription revenue\b` | `Subscription revenue` |
| I21 | `\bcash (balance|flow|in hand|at bank|generated|receipts)\b` | `Cash balance`, `Cash flow`, `Cash in hand`, `Cash at bank`, `Cash generated`, `Cash receipts` |
| I22 | `\boccupancy\b` | `Occupancy`, `Hotel occupancy` |
| I23 | `\butili(s|z)ation\b` | `Utilisation`, `Utilization`, `Bed utilisation` |
| I24 | `\bheadcount\b` | `Headcount`, `Group headcount` |
| I25 | `\bfte\b` | `FTE`, `Sales FTE` |
| I26 | `\bbooking(s)?\b` | `Booking`, `Bookings` |
| I27 | `\borders?\b` | `Order`, `Orders` |
| I28 | `\bunits sold\b` | `Units sold` |
| I29 | `\bactivation\b` | `Activation`, `% Activation` |
| I30 | `\bretention\b` | `Retention`, `Net retention` |
| I31 | `\brenewal(s)?\b` | `Renewal`, `Renewals` |
| I32 | `\bupsell\b` | `Upsell`, `Upsell rate` |
| I33 | `\bgrant\b` | `Grant`, `Government grant` |
| I34 | `\bdonation(s)?\b` | `Donation`, `Donations` |
| I35 | `\bfundraising\b` | `Fundraising` |
| I36 | `\bequity\b` | `Equity`, `Shareholders equity` |
| I37 | `\binvestment\b` | `Investment`, `New investment` |
| I38 | `\bltv\b` | `LTV`, `Customer LTV` |
| I39 | `\bnrr\b` | `NRR`, `Logo NRR` |
| I40 | `\bfcf\b` | `FCF`, `Levered FCF` |
| I41 | `\bfree cash\b` | `Free cash`, `Free cash flow` |
| I42 | `\binterest income\b` | `Interest income` |
| I43 | `\binterest received\b` | `Interest received` |
| I44 | `\bgain(s)?\b` | `Gain`, `Gains`, `FX gains` |
| I45 | `\bads? (revenue|income|fill rate)\b` | `Ad revenue`, `Ads revenue`, `Ad income`, `Ads income`, `Ad fill rate`, `Ads fill rate` |
| I46 | `\baffiliates? revenue\b` | `Affiliate revenue`, `Affiliates revenue` |
| I47 | `\bcommission revenue\b` | `Commission revenue` |
| I48 | `\bdays sales outstanding\b` | `Days sales outstanding` |
| I49 | `\bdso\b` | `DSO`, `Trade DSO` |
| I50 | `\bdays inventory outstanding\b` | `Days inventory outstanding` |
| I51 | `\bdio\b` | `DIO` |
| I52 | `\bnumber of (customers|clients|users|members|bookings|orders|deals)\b` | `Number of customers`, `Number of clients`, `Number of users`, `Number of members`, `Number of bookings`, `Number of orders`, `Number of deals` |
| I53 | `\bimpressions\b` | `Impressions` |
| I54 | `\bclicks?\b` | `Click`, `Clicks` |
| I55 | `\bleads?\b` | `Lead`, `Leads` |
| I56 | `\baverage (revenue|arpu|arpc|arr|order value|selling price|basket|booking value)\b` | `Average revenue`, `Average ARPU`, `Average ARPC`, `Average ARR`, `Average order value`, `Average selling price`, `Average basket`, `Average booking value` |
| I57 | `\baverage daily rate\b` | `Average daily rate` |
| I58 | `\badr\b` | `ADR` |
| I59 | `\brevpar\b` | `RevPAR` |

---

## D. Default when no pattern matched

If none of the nonsense, decrease, or increase patterns match, the heuristic defaults to:

`increase`

### Example names that would fall through to default

- `Widget KPI`
- `North America`
- `bndhbrevenue` *(does not match `\brevenue\b` because `revenue` is glued inside a token)*
- `Series A`

---

## Summary

### Forced `increase`
- Nonsense / placeholder / test-like indicator names
- Non-semantic values like only punctuation or only digits

### `decrease`
- Costs, expenses, liabilities, taxes, payroll, refunds, discounts, returns, debt-like measures, and other outflow / burden indicators

### `increase`
- Revenue, income, profit, growth, customers, bookings, cash generation, retention, and other performance / scale indicators

### Default
- `increase`
