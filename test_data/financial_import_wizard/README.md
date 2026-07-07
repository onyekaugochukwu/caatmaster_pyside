# Financial Data Import Wizard - Test Files

Four synthetic files for testing the Financial Data Import Wizard
end-to-end (sidebar → "Import Financial Data..." icon next to the
dataset list). Each is deliberately messy in the specific way that
document type actually shows up in practice - open each with the
matching document type selected and click "Detect Structure".

## gl_je_detail.xlsx → **General Ledger / Journal Entry Detail**
12 journal entries, 2 lines each (24 rows). `JE Number`, `Entry Date`,
`Description`, and `Prepared By` are populated only on each entry's
first line (blank on the continuation line) - the wizard should propose
forward-filling all four. `Debit`/`Credit` are separate columns - the
wizard should propose collapsing them into one signed `amount` column.
Also includes a few deliberate audit-relevant quirks for future Journal
Entry Testing work: a weekend posting (JE1006, Saturday Jan 20), a
round-dollar entry (JE1009, exactly $10,000), a "reclass"/override entry
prepared by "CFO Override" (JE1004), and a period-end accrual (JE1010,
Jan 31).

## trial_balance.xlsx → **Trial Balance**
21 rows, Account/Debit/Credit columns. The `Account` column encodes a
3-level hierarchy via indentation (`Assets` → `  Current Assets` →
`    Cash`), including pure category/subtotal rows with no amount of
their own ("Assets", "Total Current Assets"). The wizard should propose
collapsing Debit/Credit into a signed `amount` and extracting the
indentation into an `account_level` column.

## financial_statement.xlsx → **Financial Statement**
A 3-month income statement, wide format (`Jan-24`/`Feb-24`/`Mar-24` as
separate columns) with the same kind of indentation hierarchy as the
trial balance. The wizard should propose extracting the hierarchy level
*and* unpivoting the three period columns into a tidy
`(Line Item, period, amount)` table.

## chart_of_accounts.xlsx → **Chart of Accounts**
15 accounts, no transactional amounts - just `Account Name` (indented
hierarchy), `Account Number`, and `Account Type`. The wizard should
propose extracting the hierarchy level only.
