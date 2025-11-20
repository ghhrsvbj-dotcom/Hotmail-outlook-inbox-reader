import { chromium } from "playwright-core";
import dotenv from "dotenv";

dotenv.config();

const URL =
  "https://accounts.google.com/v3/signin/identifier?" +
  "continue=https%3A%2F%2Fmail.google.com%2Fmail%2F&" +
  "dsh=S1157872587%3A1760592988268952&ec=asw-gmail-globalnav-signin&" +
  "flowEntry=AccountChooser&flowName=GlifWebSignIn&service=mail";

const OTP_PATTERN = /\b(\d{5,9})\b/g;
const FACEBOOK_KEYWORDS = ["facebook", "meta"];
const CONFIRMATION_KEYWORDS = ["confirmation code"];
const IGNORED_CODES = new Set(["94025"]);

async function clickOptionalConfirm(page, timeoutMs = 5000) {
  const selectors = ["input#confirm", 'input[name="confirm"]', 'input[type="submit"]'];
  const deadline = Date.now() + timeoutMs;
  for (const selector of selectors) {
    const remaining = Math.max(deadline - Date.now(), 0);
    if (remaining <= 0) break;
    const handle = await page.$(selector);
    if (!handle) {
      await page.waitForTimeout(200);
      continue;
    }
    const enabled = await handle.isEnabled();
    const visible = await handle.isVisible();
    if (enabled && visible) {
      await handle.click();
      return true;
    }
  }
  return false;
}

function safeInnerText(elementHandle) {
  if (!elementHandle) return "";
  return elementHandle.innerText().catch(() => "");
}

export async function fetchInboxSummary(email, { password, maxRows = 10, headless = true }) {
  const start = performance.now();
  const result = { emails: [], first_body: "", confirm_clicked: false, errors: [] };

  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();

  try {
    await page.goto(URL, { timeout: 60000 });
    await page.fill("input#identifierId", email);
    await page.click("#identifierNext");

    await page.waitForSelector('input[name="Passwd"]', { timeout: 20000 });
    await page.fill('input[name="Passwd"]', password);
    await page.click("#passwordNext");
	await page.waitForTimeout(3000); // wait 3 seconds


    try {
      result.confirm_clicked = await clickOptionalConfirm(page);
    } catch (err) {
      result.errors.push(`Failed to interact with confirm dialog: ${err}`);
    }
    if (!result.confirm_clicked) {
      await page.goto("https://mail.google.com/mail/u/0/#inbox", { timeout: 60000 });
    }

    await page.waitForURL((url) => url.includes("mail.google.com"), { timeout: 60000 });
    await page.waitForSelector("tr.zA", { timeout: 30000 });

    const rows = await page.$$("tr.zA");
    for (const [index, row] of rows.slice(0, maxRows).entries()) {
      const senderEl = (await row.$("span.yP")) || (await row.$("span.zF"));
      const subjectEl = await row.$("span.bog");
      const snippetEl = (await row.$("span.y2")) || (await row.$("div.y6"));
      const timeEl = (await row.$("td.xW span")) || (await row.$("span.g3"));

      result.emails.push({
        index,
        sender: await safeInnerText(senderEl),
        subject: await safeInnerText(subjectEl),
        snippet: await safeInnerText(snippetEl),
        time: await safeInnerText(timeEl),
      });
    }

    if (rows.length) {
      await rows[0].click();
      await page.waitForSelector("div.a3s", { timeout: 10000 });
      const bodyEl = (await page.$("div.a3s")) || (await page.$("div.ii.gt"));
      result.first_body = bodyEl ? await safeInnerText(bodyEl) : "";
    }
  } catch (err) {
    result.errors.push(err.message || String(err));
  } finally {
    await context.close();
    await browser.close();
  }

  result.duration = (performance.now() - start) / 1000;
  return result;
}

function isFacebookConfirmation(emailInfo) {
  const combined = `${emailInfo.sender || ""} ${emailInfo.subject || ""} ${emailInfo.snippet || ""}`.toLowerCase();
  return FACEBOOK_KEYWORDS.some((k) => combined.includes(k)) &&
    CONFIRMATION_KEYWORDS.some((k) => combined.includes(k));
}

function extractCodes(text = "") {
  return Array.from(text.matchAll(OTP_PATTERN)).map((m) => m[1]);
}

export function formatSummary(summary) {
  const codes = [];
  const seen = new Set();

  for (const emailInfo of summary.emails || []) {
    if (!isFacebookConfirmation(emailInfo)) continue;
    for (const source of [emailInfo.subject, emailInfo.snippet]) {
      for (const code of extractCodes(source || "")) {
        if (!IGNORED_CODES.has(code) && !seen.has(code)) {
          seen.add(code);
          codes.push(code);
        }
      }
    }
  }

  if (summary.first_body) {
    for (const code of extractCodes(summary.first_body)) {
      if (!IGNORED_CODES.has(code) && !seen.has(code)) {
        seen.add(code);
        codes.push(code);
      }
    }
  }

  return { codes, duration: summary.duration, errors: summary.errors || [] };
}
