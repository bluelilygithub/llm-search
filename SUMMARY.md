# Curam AI Knowledge Base — Product Summary

## Who is this for?
- **Students & Educators**: Safer, clearer math help with visuals and teacher‑quality guardrails.
- **Knowledge Workers & Teams**: Ask questions across your own docs with transparent citations.
- **Admins**: Manage users, models, security, and usage at an organizational level.
- **Developers**: A pragmatic, multi‑LLM, RAG‑enabled base you can extend quickly.

## What does it do for them?
- **Answers you can trust**: Project‑aware chat that cites your sources and avoids “no access” disclaimers.
- **Better math learning**: Compute‑first steps, contradiction self‑correction, beginner‑first teaching, and one‑click charts.
- **Faster workflows**: Voice input/output, semantic search, and clean UI for projects, tags, and cloning.
- **Personalized tone**: An adaptive profile (opt‑in) that gradually tunes verbosity to how you interact.
- **Frictionless demo**: One‑click demo guest with clear restrictions and automatic cleanup.

## What it does (features)
- **Multi‑LLM Chat**: OpenAI (GPT‑4o/mini), Anthropic Claude 3.5/4, Google Gemini, HF models; safe fallbacks and logging.
- **RAG on Your Docs**: Document uploads, embeddings, semantic search, context injection, and source scores.
- **Project‑Aware Responses**: Always inject concise project context to guide the model.
- **Education‑ready Math Mode**:
  - Teacher‑quality guardrails (compute‑first, verify, self‑correct)
  - Beginner‑first methods (y=mx+b, Keep‑Flip‑Change)
  - Core follow‑ups highlighted (explain younger, practical example, try similar) + “Illustrate this…” chart button
- **On‑Demand Visuals**: POST `/api/visualize` returns a base64 PNG (e.g., a pie chart for 94% smartphone ownership).
- **Project‑based Quizzes**: Year/subject‑aware 5‑question quizzes; durable results and progress summary.
- **Demo Guest Mode**: `/auth/guest-login` creates a TTL sandbox; banner shows expiry and restrictions; optional purge on logout.
- **Voice UX**: Robust STT/ TTS, with one auto‑retry on “no‑speech”.
- **Organization & Search**: Projects, tags, powerful conversation search (with semantic toggle).
- **Cloning**: Duplicate a project’s setup in one click (no conversation leakage).
 - **Admin Filtering**: Admins can filter projects and conversations by user; cards show owner/user info.
 - **Mathematics Personas & Seeding**:
   - Upsert seven core personas (Number & Algebra; Functions & Graphs; Measurement & Geometry; Statistics & Probability; Financial Mathematics; Discrete & Modelling; Extension/Pre‑Calculus)
   - Create projects per persona for a user
   - Seed subtopic chats per project (prompt: “Explain what is meant by {subtopic}.”)
 - **Projects Grid UX**: Grid caps at 4 columns for clarity on desktop (responsive downscale).

## How it works (high level)
1. **Frontend (Flask templates + JS)**
   - Renders chat, projects, context panes, settings; streams results and follow‑ups.
   - Adds math visuals on demand, and highlights core math follow‑ups.
2. **Chat Orchestration (Flask)**
   - Builds messages with: user profile → project context → guardrails → history → user input.
   - Routes to selected LLM provider via a unified service; tracks tokens and cost.
3. **RAG Pipeline (Simple, Document‑only)**
   - Embeds uploaded docs; performs cosine similarity server‑side; injects relevant snippets and source info.
4. **Adaptive Profile (v1, opt‑in)**
   - EMA nudges verbosity from signals like “shorter/tl;dr” or “more detail/steps”; explicit settings always win.
5. **Visuals Service**
   - `MathVisualizer` (matplotlib) generates explanatory diagrams/charts; endpoint returns base64 for inline display.
6. **Demo Guest Lifecycle**
   - Guest login gated by DEMO_MODE; TTL via preferences.expires_at; optional purge on logout with DEMO_PURGE_ON_LOGOUT=true.
7. **Assessment & Progress**
   - Quizzes generated from project subject/year (NSW topic hints). Results saved to `quiz_attempts`/`quiz_answers`.
   - Progress shows latest quiz, per‑topic quiz mastery, history and details; math topics blend quiz correctness into signals.

## Technical skills, discipline, and compute
- **Stack**: Flask, SQLAlchemy, PostgreSQL, JS/CSS (no SPA), matplotlib, OpenAI/Anthropic/Gemini/HF APIs.
- **Security**: Role‑based access, CSRF where appropriate (CSRF‑exempt DELETE for REST correctness), CORS headers, input sanitization.
- **Demo Controls**: Feature flags (DEMO_MODE, DEMO_GUEST_TTL_HOURS, DEMO_PURGE_ON_LOGOUT), guest upload/model restrictions.
- **Operational Quality**: Rate limiting, structured logging, error capture, usage analytics, and stable fallbacks.
- **Prompt Engineering**: Layered system prompts (user profile, project context, math guardrails) with strict formatting rules.
- **Data Discipline**: JSONB preferences, conservative adaptive updates (EMA, caps, opt‑in, reset), source transparency for RAG.
- **Assessment Schema**: Normalized quiz attempts/answers tables; history and detail endpoints for analytics.
- **Deployment**: Procfile (Gunicorn), Railway/Heroku‑ready, environment‑based config.

## Why teams adopt it
- **Pragmatic reliability** (simple, stable RAG) + **strong UX** (project context, math guardrails, visuals) + **governance** (roles, logs).
- Extensible: add models, swap RAG backends later, extend prompts and UI without a heavy framework rewrite.

## Fast demo path
1. Create a project and upload a couple of PDFs.
2. Ask a domain question; observe cited sources.
3. Ask a math/statistics question; click “Illustrate this…” to see inline charts.
4. Click “Quiz Me” on a project; complete 5 MCQs; view Progress → Quiz History and details.
5. Toggle adaptive profile; ask for “shorter” or “more detail” and see tone adjust over time.
6. Try the demo guest flow; observe the banner and restricted actions.


