# AI Chatbot Backend

Custom AI-powered chatbot backend that handles customer inquiries 24/7
for businesses. Built with Flask, integrated with AI
providers (Claude/ Gemini/ DeepSeek), deployed on Render.

## What It Does

- Handles common customer questions automatically (hours, services,
  pricing, booking, eligibility)
- Works 24/7 — captures leads and answers questions outside business hours
- Supports Claude, Gemini, and DeepSeek — provider selected during
  setup based on your budget and needs
- Session-based conversation memory so customers can have natural
  back-and-forth conversations
- Custom system prompts tailored to each client's business
- Admin panel where you can review real customer conversations and
  see exactly what your clients are asking about

## Tech Stack

- **Backend:** Python (Flask)
- **Database:** PostgreSQL
- **AI Providers:** Anthropic Claude / Google Gemini / DeepSeek
- **Deployment:** Render
- **Frontend Widget:** Vanilla JavaScript (embeddable via CDN)

## Safety Features

- **Trigger-word filtering:** high-risk topics are detected before
  reaching the AI model, returning a pre-written safety response
  that directs the user to contact the business directly
- **System prompt hardening:** narrow scope defined per client so
  the chatbot stays on-topic and refuses out-of-scope requests
- **Rate limiting** on all API endpoints to prevent spam and abuse
- **Request logging** for monitoring and manual review
- **Visible disclaimers** on the chat widget

