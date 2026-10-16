# AI Infrastructure Credit Risk Engine

## About me
- I'm a first-year finance student and a **complete beginner at coding**.
- I understand basic finance ideas (cash flow, debt, interest), but not programming jargon.

## How to work with me
- **Explain everything in plain English.** Define any technical term the first time you use it (e.g. "a *function* is a reusable block of code that...").
- **Build in small steps.** One small piece at a time, and check that it works before moving on. Don't write lots of files at once.
- Before each step, say **what** you're about to do and **why**, in a sentence or two.
- After each step, tell me **how to check it worked** (what to run, what I should see).
- Connect code back to the finance idea it represents (e.g. "this line is the debt service coverage ratio").
- Prefer simple, readable code over clever code. Add short comments explaining the *finance* meaning.
- Ask me before installing anything, committing, or pushing to GitHub.
- If I'm about to make a decision that matters, give me your recommendation and the reason, not a long list of options.

## Project
A Python Monte Carlo simulator that models CoreWeave's cash flows and debt, stress-tests them under scenarios
(major customer loss, faster GPU depreciation, refinancing rate spikes), and estimates the probability of default.

## Setup facts
- Run Python with `python3` (plain `python` doesn't exist on this Mac).
- GitHub repo: https://github.com/gabakeller-del/AI-credit-risk-engine
- All assumptions (revenue, debt, rates) are stored in config files, not hard-coded, and each one notes its source.
