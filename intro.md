# Welcome to Curam AI Knowledge Base

Curam AI is a multi‑LLM, project‑based chat app that helps you ask better questions, learn faster (especially math), and get answers grounded in your own documents.

## What you can do
- Chat with top models (OpenAI, Claude, Gemini, HF) in one place
- Organize everything into Projects and Conversations
- Upload PDFs/DOCs and get answers with cited snippets
- Learn math with teacher‑quality guardrails and one‑click visuals
- Take 5‑question quizzes per project and track progress over time

## Quick start (first time)
1) Create a Project (sidebar → Projects → New Project)
2) Start a Chat
   - Ask anything, or
   - Click the “Illustrate this…” button on math answers for a quick chart
3) Add Documents (Context panel) to ground answers in your files
4) Try “Quiz Me” on a project (5 MCQs). See scores in Progress.

## For Students (Math mode)
- Explanations are age‑appropriate, compute‑first, and self‑correct contradictions
- Follow‑up buttons help you ask for “explain younger,” “try similar,” or “more detail”
- Visuals: on‑demand diagrams and charts for math/stats answers

## For Admins
- Filter Projects/Conversations by user from the sidebar
- Personas (Settings → Personas):
  - Seed seven Mathematics personas
  - Create one project per persona for a student
  - Seed subtopic chats in those projects (ready to learn)

Key admin endpoints (POST):
- /admin/ensure_math_personas – upsert the seven Mathematics personas
- /admin/create_math_projects_for_user – { username | user_id } → one project per persona
- /admin/seed_math_subtopics_for_user – { username | user_id } → one chat per subtopic per project

## Tips
- Project context is always injected to keep answers on‑task
- Use tags for quick grouping; search by title/content/tags
- Voice: mic for input; speaker to listen

## Need help?
- See README for full features and API list
- Or contact your admin/maintainer
