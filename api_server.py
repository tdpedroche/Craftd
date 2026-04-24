#!/usr/bin/env python3
import json, os, sqlite3, threading
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

import stripe
from anthropic import Anthropic
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID       = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
BASE_URL              = os.environ.get("BASE_URL", "http://localhost:10000")

stripe.api_key = STRIPE_SECRET_KEY

DB_PATH = "/tmp/craftd.db"

def get_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            goal TEXT, pain TEXT, experience TEXT,
            time_available TEXT, usecase TEXT,
            playbook TEXT, stripe_session TEXT UNIQUE,
            checkout_url TEXT, paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

GOAL_LABELS = {
    "make-money": "make money or grow their income",
    "save-time":  "save time at work or home",
    "learn-skills": "learn new skills and grow professionally",
    "daily-life": "simplify their everyday life",
}
PAIN_LABELS = {
    "overwhelmed": "feels overwhelmed and doesn't know where to start with AI",
    "no-time":     "doesn't have enough time to get everything done",
    "stuck":       "feels stuck and isn't making progress toward their goals",
    "results":     "isn't seeing results from what they're already trying",
}
EXP_LABELS = {
    "none":    "a total beginner who has barely used any AI tools",
    "little":  "a beginner who has tried ChatGPT a couple of times",
    "some":    "has some experience and uses AI occasionally but not consistently",
    "regular": "a regular user who uses AI tools a few times a week",
}
TIME_LABELS = {
    "5-10":  "5–10 minutes", "15-30": "15–30 minutes",
    "30-60": "30–60 minutes", "60+":   "more than an hour",
}
USECASE_LABELS = {
    "writing":  "writing, emails, content creation, and communication",
    "business": "business planning, strategy, and analysis",
    "creative": "creative projects, art, music, and ideas",
    "personal": "personal habits, health, learning, and life admin",
}

def build_prompt(answers):
    goal    = GOAL_LABELS.get(answers.get("goal",""), answers.get("goal",""))
    pain    = PAIN_LABELS.get(answers.get("pain",""), answers.get("pain",""))
    exp     = EXP_LABELS.get(answers.get("experience",""), answers.get("experience",""))
    time_av = TIME_LABELS.get(answers.get("time",""), answers.get("time",""))
    usecase = USECASE_LABELS.get(answers.get("usecase",""), answers.get("usecase",""))
    return f"""You are Craftd, an AI tool that creates personalized AI playbooks for everyday people.

Generate a complete, highly personalized AI playbook for someone with this profile:
- Main goal: They want to {goal}
- Biggest pain point: This person {pain}
- AI experience level: They are {exp}
- Time available daily: {time_av} per day
- Primary use area: {usecase}

Write a warm, encouraging, beginner-friendly playbook with these exact sections:

# Your Personal AI Playbook

## How AI Fits Into Your Life
[2-3 sentences, personal and immediately relevant]

## Your Daily AI Workflow
[3-5 numbered steps, concrete and specific, name the actual tool]

## Your Copy-Paste Prompts
[5 prompts formatted as:
**Prompt N: Title**
[Full prompt with [brackets] for fill-ins]
*When to use: one sentence*]

## Real Output Examples
[2 before/after examples. Label: "You type:" and "AI produces:"]

## Your Week-One Action Plan
[Mon-Fri, one task per day under 10 min, use ☐ checkboxes]

## Your Biggest Shortcut
[1 paragraph of direct, specific advice]

Keep under 800 words. Use "you" throughout. No jargon. Every section immediately actionable."""

def generate_and_save(lead_id, answers, email):
    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": build_prompt(answers)}],
        )
        playbook_text = message.content[0].text

        if STRIPE_SECRET_KEY and STRIPE_PRICE_ID:
            base = os.environ.get("BASE_URL", "https://craftd.onrender.com").rstrip('/')
            success_url = base + '/playbook.html?session_id={CHECKOUT_SESSION_ID}'
            cancel_url  = base + '/#quiz'
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
                mode="payment",
                customer_email=email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"email": email},
            )
            stripe_session_id = session.id
            checkout_url = session.url
            paid = 0
        else:
            stripe_session_id = f"dev_{email.replace('@','_').replace('.','_')}"
            checkout_url = f"/playbook.html?session_id={stripe_session_id}"
            paid = 1

        db = get_db()
        db.execute(
            "UPDATE leads SET playbook=?, stripe_session=?, checkout_url=?, paid=? WHERE id=?",
            (playbook_text, stripe_session_id, checkout_url, paid, lead_id),
        )
        db.commit()
        db.close()
    except Exception as e:
        db = get_db()
        db.execute("UPDATE leads SET checkout_url=? WHERE id=?", (f"error:{e}", lead_id))
        db.commit()
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class SubmitRequest(BaseModel):
    email: str
    goal: Optional[str] = None
    pain: Optional[str] = None
    experience: Optional[str] = None
    time: Optional[str] = None
    usecase: Optional[str] = None

@app.post("/api/submit")
async def submit(body: SubmitRequest):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO leads (email, goal, pain, experience, time_available, usecase) VALUES (?,?,?,?,?,?)",
        (body.email, body.goal, body.pain, body.experience, body.time, body.usecase),
    )
    lead_id = cursor.lastrowid
    db.commit()
    db.close()
    answers = {"goal": body.goal, "pain": body.pain, "experience": body.experience, "time": body.time, "usecase": body.usecase}
    threading.Thread(target=generate_and_save, args=(lead_id, answers, body.email), daemon=True).start()
    return {"pending_id": lead_id}

@app.get("/api/status")
async def get_status(pending_id: int):
    db = get_db()
    row = db.execute("SELECT checkout_url FROM leads WHERE id=?", (pending_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    url = row["checkout_url"]
    if url is None:
        return {"ready": False, "checkout_url": None, "error": None}
    if url.startswith("error:"):
        return {"ready": False, "checkout_url": None, "error": url[6:]}
    return {"ready": True, "checkout_url": url, "error": None}

@app.get("/api/playbook")
async def get_playbook(session_id: str):
    db = get_db()
    row = db.execute("SELECT id, email, playbook, paid FROM leads WHERE stripe_session=?", (session_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    if not row["paid"] and STRIPE_SECRET_KEY:
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid":
                db2 = get_db()
                db2.execute("UPDATE leads SET paid=1 WHERE id=?", (row["id"],))
                db2.commit()
                db2.close()
            else:
                raise HTTPException(status_code=402, detail="Payment not confirmed.")
        except stripe.error.StripeError:
            raise HTTPException(status_code=402, detail="Could not verify payment.")
    return {"email": row["email"], "playbook": row["playbook"]}

@app.post("/api/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        event = json.loads(payload)
    if event["type"] == "checkout.session.completed":
        sid = event["data"]["object"]["id"]
        db = get_db()
        db.execute("UPDATE leads SET paid=1 WHERE stripe_session=?", (sid,))
        db.commit()
        db.close()
    return {"received": True}

@app.get("/api/health")
async def health():
    return {"status": "ok", "stripe": bool(STRIPE_SECRET_KEY)}

# Serve static files
app.mount("/", StaticFiles(directory=".", html=True), name="static")
