import os
import json
import re
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "8950816459:AAEsSJiJiHMjg1gTGV1eKRbcBAJJKSqjXV0"
GEMINI_KEY = "AIzaSyBrHuAQ.Ab8RN6JTGegWIXbExpcVyOh0jtbwhZzpniGEumokaJ-U7CPgSA"

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── SYSTEM PROMPTS ───────────────────────────────────────────────────────────
RESEARCH_PROMPT = """You are an expert organic dropshipping product researcher. The seller runs AI-generated emotional "handmade small business pity" video ads on TikTok, Instagram Reels, and Facebook. Ad formats: "no one came to the sale", "parent in car emotional plea", "making by hand", "mean comment reaction". Product positioned as handmade. Core demo: 16-28 aesthetic women (coquette/soft girl/cottagecore). Also must appeal to Facebook parent/gift buyers. COGS under $15, sell $35-50. Product MUST look handmade-believable (yarn/fabric/flowers NOT electronics/plastic).

Return ONLY a valid JSON array of 5 products. Raw JSON only, no markdown.
Schema: [{"name":"product name","search":"aliexpress search query","cogs":"$X-Y","sell":"$XX-XX","margin":"Xx","competition":"Low|Medium|High","verdict":"GO|CONDITIONAL GO|NO GO","flag":"warning or empty","c":{"content":1,"margin":1,"timing":1,"demo":1,"pity":1,"table":1,"broad":1,"handmade":1},"angle":"one sentence emotional content angle","format":"best ad format name"}]
Scoring 1-5: content=scroll-stop, margin=price ratio, timing=market timing, demo=audience fit, pity=pity format fit, table=table display, broad=gift/FB appeal, handmade=believability"""

WINNER_PROMPT = """You are an elite dropshipping product strategist. Reverse-engineer winning products at a psychological and strategic level.
Return ONLY a valid JSON object. Raw JSON only, no markdown.
Schema: {"product_name":"name","why_it_won":{"core_trigger":"psychological trigger","scroll_stop":"visual hook","demo_insight":"who bought and why","ad_format_fit":"why pity format worked","margin_reason":"why price point worked","timing":"why timing was right"},"niche_breakdown":{"emotional_territory":"deeper emotional space","identity_purchase":"identity they were buying","adjacent_desires":["d1","d2","d3"],"lifecycle_stage":"Early|Growing|Peak|Declining","lifecycle_reason":"reason"},"winning_dna":["element1","element2","element3","element4"],"variants":[{"name":"variant name","search":"aliexpress search query","why_it_inherits":"reason","new_angle":"new audience or angle","risk":"main risk","verdict":"GO|CONDITIONAL GO|NO GO","score":8,"cogs":"$X-Y","sell":"$XX-XX"}],"dont_repeat":["trap1","trap2","trap3"]}"""

HOOKS_PROMPT = """You write viral emotional pity hooks for handmade small business TikTok/Reels. Format: young creator + supportive parent, product looks handmade, story around rejection/no sales/family support. Casual iPhone vibes, NOT commercial. Write exactly 5 hooks numbered 1-5, each 1-2 sentences."""

SCRIPT_PROMPT = """You write full scene-by-scene video scripts for emotional handmade pity ads. Include: scene setup, character actions, minimal realistic dialogue, CapCut text overlay suggestions, CTA. Use clear scene labels."""

# ─── GEMINI CALL ──────────────────────────────────────────────────────────────
def ask_gemini(system, message):
    full_prompt = f"{system}\n\nUser request: {message}"
    response = model.generate_content(full_prompt)
    return response.text

# ─── FORMAT HELPERS ───────────────────────────────────────────────────────────
def stars(n):
    return "★" * n + "☆" * (5 - n)

def verdict_emoji(v):
    if v == "GO": return "✅"
    if v == "CONDITIONAL GO": return "⚠️"
    return "❌"

def format_product_card(p, i):
    ts = sum(p["c"].values())
    v = p["verdict"]
    ali_url = f"https://www.aliexpress.com/w/wholesale-{p['search'].replace(' ', '-')}.html"
    amz_url = f"https://www.amazon.com/s?k={requests.utils.quote(p['search'])}"
    
    card = f"""
{verdict_emoji(v)} *{p['name']}*
`{v} · {ts}/40`

💰 COGS: `{p['cogs']}` | Sell: `{p['sell']}` | Margin: `{p['margin']}`
📊 Competition: `{p['competition']}`
{f"⚠️ _{p['flag']}_" if p['flag'] else ""}

*Scores:*
Content {stars(p['c']['content'])} | Margin {stars(p['c']['margin'])}
Timing {stars(p['c']['timing'])} | Demo {stars(p['c']['demo'])}
♥ Pity {stars(p['c']['pity'])} | ⊞ Table {stars(p['c']['table'])}
⊕ Broad {stars(p['c']['broad'])} | ✦ Handmade {stars(p['c']['handmade'])}

🎯 *Angle:* _{p['angle']}_
📹 *Best format:* `{p['format']}`

🛒 [AliExpress]({ali_url}) | 📦 [Amazon]({amz_url})"""
    return card.strip()

def format_winner_result(r):
    w = r["why_it_won"]
    n = r["niche_breakdown"]
    
    result = f"""
🏆 *{r['product_name']} — Winner Analysis*

━━━━━━━━━━━━━━
🧠 *WHY IT WON*
━━━━━━━━━━━━━━
🎯 Core trigger: _{w['core_trigger']}_
👁 Scroll-stop: _{w['scroll_stop']}_
👥 Demo insight: _{w['demo_insight']}_
🎭 Ad format fit: _{w['ad_format_fit']}_
💰 Margin reason: _{w['margin_reason']}_
⏰ Timing: _{w['timing']}_

━━━━━━━━━━━━━━
🎯 *NICHE BREAKDOWN*
━━━━━━━━━━━━━━
🌊 Territory: _{n['emotional_territory']}_
🪞 They were buying: *{n['identity_purchase']}*
💭 Adjacent desires: {' | '.join(n['adjacent_desires'])}
📈 Lifecycle: *{n['lifecycle_stage']}* — _{n['lifecycle_reason']}_

━━━━━━━━━━━━━━
🧬 *WINNING DNA*
━━━━━━━━━━━━━━
{chr(10).join([f"✓ {d}" for d in r['winning_dna']])}

━━━━━━━━━━━━━━
🔀 *VARIANTS TO TEST*
━━━━━━━━━━━━━━"""

    for v in r["variants"]:
        ali_url = f"https://www.aliexpress.com/w/wholesale-{v['search'].replace(' ', '-')}.html"
        result += f"""
{verdict_emoji(v['verdict'])} *{v['name']}* `{v['score']}/10`
↑ Inherits: _{v['why_it_inherits']}_
→ New angle: _{v['new_angle']}_
⚠ Risk: _{v['risk']}_
💰 `{v['cogs']}` → `{v['sell']}`
🛒 [Find on AliExpress]({ali_url})
"""

    result += f"""
━━━━━━━━━━━━━━
⚠️ *TRAPS TO AVOID*
━━━━━━━━━━━━━━
{chr(10).join([f"✕ {d}" for d in r['dont_repeat']])}"""

    return result.strip()

# ─── COMMAND HANDLERS ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """👋 *Welcome to DropResearch Bot!*

Your AI-powered organic dropshipping research assistant — built for the emotional handmade pity ad format.

*Commands:*
🔍 `/research [keyword]` — Score 5 products
🏆 `/winner [product description]` — Full winner analysis
🪝 `/hooks [product name]` — 5 viral pity hooks
📝 `/script [product name]` — Full video script
❓ `/help` — Show all commands

*Quick examples:*
`/research crochet bag`
`/winner knit heart tote bag sold on TikTok for 5 figures`
`/hooks crochet flower bouquet`

Let's find your next winner 🔥"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """*DropResearch Bot — Commands*

🔍 `/research [keyword]`
Search any keyword and get 5 products scored for your emotional handmade format
_Example: /research crochet skull cap_

🏆 `/winner [product description]`
Full psychological reverse-engineering of any winning product + variants
_Example: /winner knit heart tote bag, 5 figures on TikTok_

🪝 `/hooks [product name]`
5 viral emotional pity hooks ready to use
_Example: /hooks crochet flower bouquet_

📝 `/script [product name]`
Full "no one came to the sale" scene-by-scene video script
_Example: /script knit heart tote bag_

💡 *Tips:*
• More detail in /winner = deeper analysis
• Use /research first to find products, then /hooks or /script to create content
• All results include direct AliExpress links"""
    await update.message.reply_text(msg, parse_mode="Markdown")

async def research(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/research [keyword]`\nExample: `/research crochet bag`", parse_mode="Markdown")
        return
    
    keyword = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Researching *{keyword}*...", parse_mode="Markdown")
    
    try:
        txt = ask_gemini(RESEARCH_PROMPT, f'Keyword: "{keyword}"')
        match = re.search(r'\[[\s\S]*\]', txt)
        if not match:
            raise Exception("No JSON found in response")
        products = json.loads(match.group())
        
        await msg.edit_text(f"✅ Found *{len(products)} products* for _{keyword}_\n\nSending results...", parse_mode="Markdown")
        
        for i, p in enumerate(products):
            card = format_product_card(p, i)
            keyboard = [
                [
                    InlineKeyboardButton("🪝 Write Hooks", callback_data=f"hooks|{p['name']}"),
                    InlineKeyboardButton("📝 Full Script", callback_data=f"script|{p['name']}"),
                ],
                [InlineKeyboardButton("🏆 Winner Analysis", callback_data=f"winner|{p['name']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(card, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)
            
    except Exception as e:
        await msg.edit_text(f"❌ Research failed: {str(e)}\n\nTry again with a different keyword.")

async def winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/winner [product description]`\nExample: `/winner knit heart tote bag, sold on TikTok for 5 figures`", parse_mode="Markdown")
        return
    
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"🏆 Analyzing winner: *{product}*...", parse_mode="Markdown")
    
    try:
        txt = ask_gemini(WINNER_PROMPT, f"Winning product: {product}")
        match = re.search(r'\{[\s\S]*\}', txt)
        if not match:
            raise Exception("No JSON found")
        result = json.loads(match.group())
        
        formatted = format_winner_result(result)
        
        # Split if too long for Telegram
        if len(formatted) > 4000:
            parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(formatted, parse_mode="Markdown", disable_web_page_preview=True)
        
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Analysis failed: {str(e)}\n\nTry again with more product details.")

async def hooks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/hooks [product name]`\nExample: `/hooks crochet flower bouquet`", parse_mode="Markdown")
        return
    
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"🪝 Writing hooks for *{product}*...", parse_mode="Markdown")
    
    try:
        txt = ask_gemini(HOOKS_PROMPT, f'Write 5 viral emotional pity hooks for: {product}. Mix formats: "no one came to the sale", "parent in car", "mean comment reaction", "parent asking viewers to comment".')
        await msg.edit_text(f"🪝 *Hooks — {product}*\n\n{txt}", parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

async def script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/script [product name]`\nExample: `/script knit heart tote bag`", parse_mode="Markdown")
        return
    
    product = " ".join(context.args)
    msg = await update.message.reply_text(f"📝 Writing script for *{product}*...", parse_mode="Markdown")
    
    try:
        txt = ask_gemini(SCRIPT_PROMPT, f'Write a full "no one came to the sale" video script for: {product}. Include scene description, actions, minimal dialogue, CapCut text overlay suggestions, and emotional CTA.')
        
        if len(txt) > 4000:
            await msg.edit_text(f"📝 *Script — {product}* (Part 1)\n\n{txt[:4000]}", parse_mode="Markdown")
            await update.message.reply_text(f"📝 *Script — {product}* (Part 2)\n\n{txt[4000:]}", parse_mode="Markdown")
        else:
            await msg.edit_text(f"📝 *Script — {product}*\n\n{txt}", parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Failed: {str(e)}")

# ─── BUTTON CALLBACKS ─────────────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, product = query.data.split("|", 1)
    
    if action == "hooks":
        await query.message.reply_text(f"🪝 Writing hooks for *{product}*...", parse_mode="Markdown")
        try:
            txt = ask_gemini(HOOKS_PROMPT, f'Write 5 viral emotional pity hooks for: {product}.')
            await query.message.reply_text(f"🪝 *Hooks — {product}*\n\n{txt}", parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ Failed: {str(e)}")
    
    elif action == "script":
        await query.message.reply_text(f"📝 Writing script for *{product}*...", parse_mode="Markdown")
        try:
            txt = ask_gemini(SCRIPT_PROMPT, f'Write a full "no one came to the sale" video script for: {product}.')
            await query.message.reply_text(f"📝 *Script — {product}*\n\n{txt[:4000]}", parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ Failed: {str(e)}")
    
    elif action == "winner":
        await query.message.reply_text(f"🏆 Analyzing *{product}*...", parse_mode="Markdown")
        try:
            txt = ask_gemini(WINNER_PROMPT, f"Winning product: {product}")
            match = re.search(r'\{[\s\S]*\}', txt)
            if match:
                result = json.loads(match.group())
                formatted = format_winner_result(result)
                await query.message.reply_text(formatted[:4000], parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            await query.message.reply_text(f"❌ Failed: {str(e)}")

# ─── NATURAL LANGUAGE HANDLER ─────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if any(w in text for w in ["research", "find product", "search"]):
        context.args = update.message.text.split()[1:]
        await research(update, context)
    elif any(w in text for w in ["winner", "analyze", "why did"]):
        context.args = update.message.text.split()
        await winner(update, context)
    elif any(w in text for w in ["hook", "hooks"]):
        context.args = update.message.text.split()[1:]
        await hooks(update, context)
    elif any(w in text for w in ["script", "video script"]):
        context.args = update.message.text.split()[1:]
        await script(update, context)
    else:
        await update.message.reply_text(
            "I didn't understand that. Try:\n\n"
            "🔍 `/research crochet bag`\n"
            "🏆 `/winner knit tote bag 5 figures TikTok`\n"
            "🪝 `/hooks flower bouquet`\n"
            "📝 `/script crochet skull cap`",
            parse_mode="Markdown"
        )

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
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
