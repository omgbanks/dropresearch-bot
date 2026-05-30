import os
import json
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ─── CONFIG — keys loaded from environment variables, never hardcoded ──────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

def get_gemini_url():
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

# ─── SYSTEM PROMPTS ───────────────────────────────────────────────────────────
RESEARCH_PROMPT = """You are an expert organic dropshipping product researcher. The seller runs AI-generated emotional "handmade small business pity" video ads on TikTok, Instagram Reels, and Facebook. Ad formats: "no one came to the sale", "parent in car emotional plea", "making by hand", "mean comment reaction". Product positioned as handmade. Core demo: 16-28 aesthetic women (coquette/soft girl/cottagecore). Also must appeal to Facebook parent/gift buyers. COGS under $15, sell $35-50. Product MUST look handmade-believable (yarn/fabric/flowers NOT electronics/plastic).
Return ONLY a valid JSON array of 5 products. Raw JSON only, no markdown, no code blocks.
Schema: [{"name":"product name","search":"aliexpress search query","cogs":"$X-Y","sell":"$XX-XX","margin":"Xx","competition":"Low|Medium|High","verdict":"GO|CONDITIONAL GO|NO GO","flag":"warning or empty","c":{"content":1,"margin":1,"timing":1,"demo":1,"pity":1,"table":1,"broad":1,"handmade":1},"angle":"one sentence emotional content angle","format":"best ad format name"}]
Scoring 1-5: content=scroll-stop, margin=price ratio, timing=market timing, demo=audience fit, pity=pity format fit, table=table display, broad=gift/FB appeal, handmade=believability"""

WINNER_PROMPT = """You are an elite dropshipping product strategist. Reverse-engineer winning products at a psychological and strategic level.
Return ONLY a valid JSON object. Raw JSON only, no markdown, no code blocks.
Schema: {"product_name":"name","why_it_won":{"core_trigger":"psychological trigger","scroll_stop":"visual hook","demo_insight":"who bought and why","ad_format_fit":"why pity format worked","margin_reason":"why price point worked","timing":"why timing was right"},"niche_breakdown":{"emotional_territory":"deeper emotional space","identity_purchase":"identity they were buying","adjacent_desires":["d1","d2","d3"],"lifecycle_stage":"Early|Growing|Peak|Declining","lifecycle_reason":"reason"},"winning_dna":["element1","element2","element3","element4"],"variants":[{"name":"variant name","search":"aliexpress search query","why_it_inherits":"reason","new_angle":"new audience or angle","risk":"main risk","verdict":"GO|CONDITIONAL GO|NO GO","score":8,"cogs":"$X-Y","sell":"$XX-XX"}],"dont_repeat":["trap1","trap2","trap3"]}"""

HOOKS_PROMPT = """You write viral emotional pity hooks for handmade small business TikTok/Reels. Format: young creator + supportive parent, product looks handmade, story around rejection/no sales/family support. Casual iPhone vibes, NOT commercial. Write exactly 5 hooks numbered 1-5, each 1-2 sentences."""

SCRIPT_PROMPT = """You write full scene-by-scene video scripts for emotional handmade pity ads. Include: scene setup, character actions, minimal realistic dialogue, CapCut text overlay suggestions, CTA. Use clear scene labels."""

# ─── GEMINI CALL ──────────────────────────────────────────────────────────────
def ask_gemini(system, message):
    payload = {
        "contents": [{"parts": [{"text": f"{system}\n\nRequest: {message}"}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4000}
    }
    response = requests.post(get_gemini_url(), headers={"Content-Type": "application/json"}, json=payload, timeout=60)
    data = response.json()
    if "error" in data:
        raise Exception(data["error"]["message"])
    return data["candidates"][0]["content"]["parts"][0]["text"]

# ─── FORMAT HELPERS ───────────────────────────────────────────────────────────
def stars(n):
    return "★" * int(n) + "☆" * (5 - int(n))

def verdict_emoji(v):
    return "✅" if v == "GO" else "⚠️" if v == "CONDITIONAL GO" else "❌"

def format_product_card(p):
    ts = sum(p["c"].values())
    v = p.get("verdict", "NO GO")
    ali = f"https://www.aliexpress.com/w/wholesale-{p['search'].replace(' ', '-')}.html"
    amz = f"https://www.amazon.com/s?k={requests.utils.quote(p['search'])}"
    flag = f"\n⚠️ _{p['flag']}_" if p.get("flag") else ""
    return f"""{verdict_emoji(v)} *{p['name']}*
`{v} · {ts}/40`
💰 COGS `{p['cogs']}` | Sell `{p['sell']}` | Margin `{p['margin']}`
📊 Competition: `{p['competition']}`{flag}

Content {stars(p['c']['content'])} | Margin {stars(p['c']['margin'])} | Timing {stars(p['c']['timing'])}
Demo {stars(p['c']['demo'])} | ♥Pity {stars(p['c']['pity'])} | ⊞Table {stars(p['c']['table'])}
⊕Broad {stars(p['c']['broad'])} | ✦Handmade {stars(p['c']['handmade'])}

🎯 *Angle:* _{p['angle']}_
📹 *Format:* `{p['format']}`
🛒 [AliExpress]({ali}) | 📦 [Amazon]({amz})""".strip()

def format_winner(r):
    w = r["why_it_won"]
    n = r["niche_breakdown"]
    lc = {"Early":"🌱","Growing":"📈","Peak":"🔥","Declining":"📉"}.get(n["lifecycle_stage"],"📊")
    text = f"""🏆 *{r['product_name']} — Winner Analysis*

━━━ 🧠 WHY IT WON ━━━
🎯 *Trigger:* _{w['core_trigger']}_
👁 *Scroll-stop:* _{w['scroll_stop']}_
👥 *Demo:* _{w['demo_insight']}_
🎭 *Ad fit:* _{w['ad_format_fit']}_
💰 *Margin:* _{w['margin_reason']}_
⏰ *Timing:* _{w['timing']}_

━━━ 🎯 NICHE ━━━
🌊 _{n['emotional_territory']}_
🪞 They bought: *{n['identity_purchase']}*
💭 {' | '.join(n['adjacent_desires'])}
{lc} *{n['lifecycle_stage']}* — _{n['lifecycle_reason']}_

━━━ 🧬 WINNING DNA ━━━
{chr(10).join([f"✓ {d}" for d in r['winning_dna']])}

━━━ 🔀 VARIANTS ━━━"""
    for v in r.get("variants", []):
        ali = f"https://www.aliexpress.com/w/wholesale-{v['search'].replace(' ', '-')}.html"
        text += f"\n{verdict_emoji(v['verdict'])} *{v['name']}* `{v['score']}/10`\n↑ _{v['why_it_inherits']}_\n→ _{v['new_angle']}_\n⚠ _{v['risk']}_\n`{v['cogs']}` → `{v['sell']}` | [AliExpress]({ali})\n"
    text += f"\n━━━ ⚠️ AVOID ━━━\n{chr(10).join([f'✕ {d}' for d in r.get('dont_repeat',[])])}"
    return text.strip()

# ─── COMMANDS ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""👋 *Welcome to DropResearch Bot!*

AI product research for your emotional handmade pity ad format.

*Commands:*
🔍 `/research [keyword]` — Score 5 products
🏆 `/winner [product]` — Full winner analysis  
🪝 `/hooks [product]` — 5 viral pity hooks
📝 `/script [product]` — Full video script

*Examples:*
`/research crochet bag`
`/winner knit heart tote bag 5 figures TikTok`
`/hooks crochet flower bouquet`

Let's find your next winner 🔥""", parse_mode="Markdown")

async def research(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/research crochet bag`", parse_mode="Markdown")
        return
    keyword = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Researching *{keyword}*...", parse_mode="Markdown")
    try:
        txt = ask_gemini(RESEARCH_PROMPT, f'Keyword: "{keyword}"')
        match = re.search(r'\[[\s\S]*\]', txt)
        if not match:
            raise Exception("No JSON found — try again")
        products = json.loads(match.group())
        await msg.edit_text(f"✅ *{len(products)} products* scored for _{keyword}_", parse_mode="Markdown")
        for p in products:
            card = format_product_card(p)
            keyboard = [[
                InlineKeyboardButton("🪝 Hooks", callback_data=f"hooks|{p['name'][:40]}"),
                InlineKeyboardButton("📝 Script", callback_data=f"script|{p['name'][:40]}"),
                InlineKeyboardButton("🏆 Analyze", callback_data=f"winner|{p['name'][:40]}")
            ]]
            await update.message.reply_text(card, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

async def winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/winner knit tote bag 5 figures TikTok`", parse_mode="Markdown")
        return
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"🏆 Analyzing *{product}*...", parse_mode="Markdown")
    try:
        txt = ask_gemini(WINNER_PROMPT, f"Winning product: {product}")
        match = re.search(r'\{[\s\S]*\}', txt)
        if not match:
            raise Exception("No JSON found")
        result = json.loads(match.group())
        formatted = format_winner(result)
        await msg.delete()
        for i in range(0, len(formatted), 4000):
            await update.message.reply_text(formatted[i:i+4000], parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

async def hooks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/hooks crochet flower bouquet`", parse_mode="Markdown")
        return
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"🪝 Writing hooks for *{product}*...", parse_mode="Markdown")
    try:
        txt = ask_gemini(HOOKS_PROMPT, f'Write 5 viral emotional pity hooks for: {product}. Mix: "no one came to the sale", "parent in car", "mean comment reaction", "parent asking viewers to comment".')
        await msg.edit_text(f"🪝 *Hooks — {product}*\n\n{txt}", parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

async def script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/script knit heart tote bag`", parse_mode="Markdown")
        return
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Writing script for *{product}*...", parse_mode="Markdown")
    try:
        txt = ask_gemini(SCRIPT_PROMPT, f'Write a full "no one came to the sale" video script for: {product}. Include scene description, actions, minimal dialogue, CapCut text overlays, emotional CTA.')
        for i in range(0, len(txt), 4000):
            if i == 0:
                await msg.edit_text(f"📝 *Script — {product}*\n\n{txt[:4000]}", parse_mode="Markdown")
            else:
                await update.message.reply_text(txt[i:i+4000], parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, product = query.data.split("|", 1)
    if action == "hooks":
        await query.message.reply_text(f"🪝 Writing hooks...", parse_mode="Markdown")
        try:
            txt = ask_gemini(HOOKS_PROMPT, f'Write 5 viral emotional pity hooks for: {product}.')
            await query.message.reply_text(f"🪝 *Hooks — {product}*\n\n{txt}", parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ {str(e)}")
    elif action == "script":
        await query.message.reply_text(f"📝 Writing script...", parse_mode="Markdown")
        try:
            txt = ask_gemini(SCRIPT_PROMPT, f'Write a full "no one came to the sale" script for: {product}.')
            await query.message.reply_text(f"📝 *Script — {product}*\n\n{txt[:4000]}", parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ {str(e)}")
    elif action == "winner":
        await query.message.reply_text(f"🏆 Analyzing...", parse_mode="Markdown")
        try:
            txt = ask_gemini(WINNER_PROMPT, f"Winning product: {product}")
            match = re.search(r'\{[\s\S]*\}', txt)
            if match:
                result = json.loads(match.group())
                formatted = format_winner(result)
                await query.message.reply_text(formatted[:4000], parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            await query.message.reply_text(f"❌ {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(w in text for w in ["research", "find product", "search for"]):
        context.args = update.message.text.split()[1:]
        await research(update, context)
    elif any(w in text for w in ["winner", "analyze", "why did"]):
        context.args = update.message.text.split()
        await winner(update, context)
    elif "hook" in text:
        context.args = update.message.text.split()[1:]
        await hooks(update, context)
    elif "script" in text:
        context.args = update.message.text.split()[1:]
        await script(update, context)
    else:
        await update.message.reply_text(
            "Try:\n🔍 `/research crochet bag`\n🏆 `/winner knit tote 5 figures`\n🪝 `/hooks flower bouquet`\n📝 `/script skull cap`",
            parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("research", research))
    app.add_handler(CommandHandler("winner", winner))
    app.add_handler(CommandHandler("hooks", hooks))
    app.add_handler(CommandHandler("script", script))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ DropResearch Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
