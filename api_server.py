#!/usr/bin/env python3
import json, os, sqlite3, threading
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

import stripe
from anthropic import Anthropic
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = "/tmp/plaax.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _use_postgres():
    return bool(DATABASE_URL and psycopg2)

def get_db():
    if _use_postgres():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db

def db_execute(conn, sql, params=()):
    """Run a query, normalising SQLite vs Postgres placeholder syntax."""
    if _use_postgres():
        # Postgres uses %s placeholders; convert from ?
        sql = sql.replace("?", "%s")
        # Postgres uses SERIAL not AUTOINCREMENT
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)

def init_db():
    conn = get_db()
    if _use_postgres():
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                first_name TEXT,
                goal TEXT, role TEXT, pain TEXT, time_drain TEXT,
                experience TEXT, tried TEXT, usecase TEXT,
                time_available TEXT, success_vision TEXT,
                playbook TEXT, stripe_session TEXT UNIQUE,
                checkout_url TEXT, paid INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                first_name TEXT,
                goal TEXT, role TEXT, pain TEXT, time_drain TEXT,
                experience TEXT, tried TEXT, usecase TEXT,
                time_available TEXT, success_vision TEXT,
                playbook TEXT, stripe_session TEXT UNIQUE,
                checkout_url TEXT, paid INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

GOAL_LABELS = {
    "make-money":    "start or grow a side income stream",
    "save-time":     "get hours of their week back",
    "learn-skills":  "build skills that make them more valuable",
    "daily-life":    "make everyday life easier and less chaotic",
    "career-growth": "advance their career or land a better job",
}
ROLE_LABELS = {
    "employee":         "a full-time employee at a company",
    "freelancer":       "a freelancer, consultant, or contractor",
    "business-owner":   "a business owner or entrepreneur",
    "student":          "a student or recent graduate",
    "parent-homemaker": "a stay-at-home parent or caregiver",
    "job-seeker":       "a job seeker or career changer",
}
PAIN_LABELS = {
    "overwhelmed":   "has too many options and doesn't know where to start",
    "no-time":       "is always busy but never feels productive",
    "stuck":         "knows what they want but can't seem to move forward",
    "results":       "tries things but nothing seems to actually work",
    "consistency":   "starts strong but struggles to stay consistent",
}
TIME_DRAIN_LABELS = {
    "emails-messages":   "emails, messages, and back-and-forth communication",
    "research-planning": "looking things up, researching, and making decisions",
    "content-writing":   "writing — posts, reports, scripts, or documents",
    "admin-tasks":       "scheduling, organizing, and repetitive busywork",
    "client-work":       "client or customer requests and follow-ups",
}
EXP_LABELS = {
    "none":     "has never really used AI tools",
    "little":   "has played around with ChatGPT once or twice",
    "some":     "uses AI casually here and there but not consistently",
    "regular":  "uses AI regularly as part of their routine",
    "advanced": "an advanced user who uses multiple tools and writes their own prompts",
}
TRIED_LABELS = {
    "nothing":         "has never tried AI at all — starting from zero",
    "basic-questions": "has chatted with AI or asked simple questions",
    "work-tasks":      "has used AI to help with a real work task",
    "multiple-tools":  "has explored several tools like ChatGPT, Midjourney, etc.",
    "built-workflow":  "has already built part of their workflow around AI",
}
USECASE_LABELS = {
    "writing":  "writing — emails, content, copy, captions, and scripts",
    "business": "business — strategy, planning, research, and analysis",
    "creative": "creative — design, music, video, ideas, and storytelling",
    "personal": "personal growth — habits, learning, health, and finance",
    "income":   "making money — freelancing, selling, or building side hustles",
}
TIME_LABELS = {
    "5-10":    "under 10 minutes a day",
    "15-30":   "15-30 minutes a day",
    "30-60":   "30-60 minutes a day",
    "60+":     "more than an hour a day",
    "varies":  "a variable amount — some days a lot, some days nothing",
}
SUCCESS_LABELS = {
    "save-10hrs":    "getting back 10+ hours a month they were wasting",
    "earn-more":     "making real extra money they weren't making before",
    "feel-confident":"feeling smarter and more capable than their peers",
    "less-stress":   "feeling calm, focused, and in control of their life",
    "career-win":    "landing a promotion, client, or opportunity they couldn't before",
}
LEARNING_LABELS = {
    "step-by-step":   "prefers exact steps they can follow without thinking",
    "examples":       "learns best by seeing real examples they can copy and tweak",
    "just-start":     "prefers to be pointed at a tool and experiment freely",
    "big-picture":    "needs to understand the big picture before diving into details",
    "accountability": "thrives with checklists and plans they can hold themselves to",
}

def build_prompt(answers):
    goal     = GOAL_LABELS.get(answers.get("goal",""), answers.get("goal",""))
    role     = ROLE_LABELS.get(answers.get("role",""), answers.get("role",""))
    pain     = PAIN_LABELS.get(answers.get("pain",""), answers.get("pain",""))
    drain    = TIME_DRAIN_LABELS.get(answers.get("time_drain",""), answers.get("time_drain",""))
    exp      = EXP_LABELS.get(answers.get("experience",""), answers.get("experience",""))
    tried    = TRIED_LABELS.get(answers.get("tried",""), answers.get("tried",""))
    usecase  = USECASE_LABELS.get(answers.get("usecase",""), answers.get("usecase",""))
    time_av  = TIME_LABELS.get(answers.get("time",""), answers.get("time",""))
    success  = SUCCESS_LABELS.get(answers.get("success",""), answers.get("success",""))
    learning = LEARNING_LABELS.get(answers.get("learning_style",""), answers.get("learning_style",""))
    return (
        "You are Plaax, an AI coach that creates deeply personalized AI playbooks for everyday people.\n\n"
        "Generate a complete, highly personalized AI playbook for someone with this exact profile:\n"
        + (("- First name: " + answers.get("first_name","").strip() + "\n") if answers.get("first_name","").strip() else "")
        + "- Life situation: They are " + role + "\n"
        "- Main goal: They want to " + goal + "\n"
        "- Biggest pain point: This person " + pain + "\n"
        "- Biggest time drain: " + drain + "\n"
        "- AI experience level: They are " + exp + "\n"
        "- What they've already tried: This person " + tried + "\n"
        "- Primary use area: " + usecase + "\n"
        "- Time available daily: " + time_av + " per day\n"
        "- 90-day success vision: They want to end up " + success + "\n"
        + (("- Learning style: This person " + learning + "\n") if learning else "")
        + "\n"
        "Write a warm, encouraging, beginner-friendly playbook with these EXACT sections. "
        "Make every single section deeply specific to this person's role, goal, and situation — "
        "not generic advice. Use their exact context throughout.\n\n"
        "# Your Personal AI Playbook\n\n"
        "## How AI Fits Into Your Life\n"
        "3-4 sentences written directly to this person. Reference their specific role and goal. "
        "Make them feel like this was written just for them.\n\n"
        "## Your Recommended AI Tools\n"
        "List 3-4 specific free AI tools that are perfect for their use case and experience level. "
        "For each tool: name, one sentence on what it does, and exactly how this person should use it. "
        "Format: **Tool Name** — what it does. How to use it for [their specific situation].\n\n"
        "## Your Daily AI Workflow\n"
        "5-6 numbered steps, completely specific to their role and time available. "
        "Name the actual tool for each step. Make it feel like a real daily routine.\n\n"
        "## Your 15 Copy-Paste Prompts\n"
        "Write exactly 15 prompts, all tailored to their use case and goal. "
        "Format each as:\n"
        "**Prompt N: [Descriptive Title]**\n"
        "[The full prompt with [BRACKETS] for parts they fill in]\n"
        "*Best for: one specific sentence about when to use this*\n\n"
        "## Real Output Examples\n"
        "3 before/after examples that are hyper-specific to their situation. "
        "Label clearly: **You type:** and **AI produces:** Show realistic, useful output.\n\n"
        "## What to Avoid (Beginner Mistakes)\n"
        "4-5 specific mistakes that are common for someone in their exact situation. "
        "Be direct and practical — tell them what goes wrong and how to fix it.\n\n"
        "## Your 30-Day Action Plan\n"
        "Break it into 4 weeks. Each week has a theme and 5 daily tasks (Mon-Fri). "
        "Tasks should be under 15 min each, use checkboxes, and build on each other progressively. "
        "Week 1 = foundations, Week 2 = building habits, Week 3 = going deeper, Week 4 = mastery.\n\n"
        "## Your Biggest Shortcut\n"
        "1-2 paragraphs of the single most powerful insight for this specific person. "
        "Based on their role, goal, and 90-day vision — what's the one thing that will make the biggest difference?\n\n"
        "Aim for 1200-1500 words total. Use 'you' throughout. Zero jargon. "
        "Every section must feel like it was written specifically for this person, not copy-pasted from a template."
    )

def generate_and_save(lead_id, answers, email):
    try:
        # Read env vars fresh inside the thread
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
        stripe_price_id   = os.environ.get("STRIPE_PRICE_ID", "")
        base_url          = os.environ.get("BASE_URL", "https://www.getplaax.com").strip().rstrip("/")

        print("DEBUG generate_and_save called", flush=True)
        print("DEBUG base_url=" + base_url, flush=True)
        print("DEBUG price_id=" + stripe_price_id, flush=True)

        # Generate playbook
        client = Anthropic(api_key=anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8000,
            messages=[{"role": "user", "content": build_prompt(answers)}],
        )
        playbook_text = message.content[0].text
        print("DEBUG playbook generated, length=" + str(len(playbook_text)), flush=True)

        # Create Stripe checkout session
        if stripe_secret_key and stripe_price_id:
            stripe.api_key = stripe_secret_key
            # Must use string concatenation so {CHECKOUT_SESSION_ID} stays literal for Stripe
            success_url = base_url + "/playbook.html?session_id=" + "{CHECKOUT_SESSION_ID}"
            cancel_url  = base_url + "/#quiz"
            print("DEBUG success_url=" + success_url, flush=True)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": stripe_price_id, "quantity": 1}],
                mode="payment",
                customer_email=email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"email": email},
            )
            stripe_session_id = session.id
            checkout_url = session.url
            paid = 0
            print("DEBUG stripe session created: " + stripe_session_id, flush=True)
        else:
            stripe_session_id = "dev_" + email.replace("@","_").replace(".","_")
            checkout_url = "/playbook.html?session_id=" + stripe_session_id
            paid = 1

        db = get_db()
        db_execute(db, "UPDATE leads SET playbook=?, stripe_session=?, checkout_url=?, paid=? WHERE id=?",
            (playbook_text, stripe_session_id, checkout_url, paid, lead_id))
        db.commit()
        db.close()
        print("DEBUG DB updated successfully", flush=True)

    except Exception as e:
        print("DEBUG ERROR: " + str(e), flush=True)
        db = get_db()
        db_execute(db, "UPDATE leads SET checkout_url=? WHERE id=?", ("error:" + str(e), lead_id))
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
    first_name: Optional[str] = None
    goal: Optional[str] = None
    role: Optional[str] = None
    pain: Optional[str] = None
    time_drain: Optional[str] = None
    experience: Optional[str] = None
    tried: Optional[str] = None
    usecase: Optional[str] = None
    time: Optional[str] = None
    success: Optional[str] = None
    learning_style: Optional[str] = None

@app.post("/api/submit")
async def submit(body: SubmitRequest):
    db = get_db()
    if _use_postgres():
        cur = db.cursor()
        cur.execute(
            "INSERT INTO leads (email, first_name, goal, role, pain, time_drain, experience, tried, usecase, time_available, success_vision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.email, body.first_name, body.goal, body.role, body.pain, body.time_drain, body.experience, body.tried, body.usecase, body.time, body.success),
        )
        lead_id = cur.fetchone()["id"]
    else:
        cursor = db.execute(
            "INSERT INTO leads (email, first_name, goal, role, pain, time_drain, experience, tried, usecase, time_available, success_vision) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (body.email, body.first_name, body.goal, body.role, body.pain, body.time_drain, body.experience, body.tried, body.usecase, body.time, body.success),
        )
        lead_id = cursor.lastrowid
    db.commit()
    db.close()
    answers = {"goal": body.goal, "role": body.role, "pain": body.pain, "time_drain": body.time_drain,
               "experience": body.experience, "tried": body.tried, "usecase": body.usecase,
               "time": body.time, "success": body.success, "first_name": body.first_name,
               "learning_style": body.learning_style}
    threading.Thread(target=generate_and_save, args=(lead_id, answers, body.email), daemon=True).start()
    return {"pending_id": lead_id}

@app.get("/api/status")
async def get_status(pending_id: int):
    db = get_db()
    row = db_execute(db, "SELECT checkout_url FROM leads WHERE id=?", (pending_id,)).fetchone()
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
    stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    db = get_db()
    row = db_execute(db, "SELECT id, email, first_name, playbook, paid FROM leads WHERE stripe_session=?", (session_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Playbook not found.")
    if not row["paid"] and stripe_secret_key:
        try:
            stripe.api_key = stripe_secret_key
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid":
                db2 = get_db()
                db_execute(db2, "UPDATE leads SET paid=1 WHERE id=?", (row["id"],))
                db2.commit()
                db2.close()
            else:
                raise HTTPException(status_code=402, detail="Payment not confirmed.")
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=402, detail="Could not verify payment: " + str(e))
    return {"email": row["email"], "first_name": row["first_name"] or "", "playbook": row["playbook"]}

@app.post("/api/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    stripe_secret_key     = os.environ.get("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    stripe.api_key        = stripe_secret_key
    payload = await request.body()
    if stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, stripe_webhook_secret)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        event = json.loads(payload)
    if event["type"] == "checkout.session.completed":
        sid = event["data"]["object"]["id"]
        db = get_db()
        db_execute(db, "UPDATE leads SET paid=1 WHERE stripe_session=?", (sid,))
        db.commit()
        db.close()
    return {"received": True}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "stripe": bool(os.environ.get("STRIPE_SECRET_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "base_url": repr(os.environ.get("BASE_URL", "NOT SET")),
    }

# Serve static files
app.mount("/", StaticFiles(directory=".", html=True), name="static")
