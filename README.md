# 🏛️ Mahavihara - Agentic AI Tutor

> *"ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."*

An adaptive AI tutoring system for Linear Algebra that uses Socratic method pedagogy, knowledge graphs with prerequisite tracing, and personalized learning prescriptions.

## 📹 Demo Video

**Watch the full demo:** [Google Drive](https://drive.google.com/file/d/13zPDN0wtoSCEaEeeQLNZvKw6jNEsy5fB/view?usp=drive_link)

## ✨ Key Features

- **Socratic Teaching Method** — Guides students with questions rather than giving answers directly
- **Knowledge Graph with Prerequisites** — Visual DAG showing concept dependencies (Vectors → Matrix Ops → Determinants → Inverse → Eigenvalues)
- **Root Cause Analysis** — When students fail, traces back through prerequisites to find the fundamental gap
- **Adaptive Testing (CAT)** — Progressive difficulty (Easy → Medium → Hard) using Item Response Theory
- **Misconception Detection** — Identifies specific misconceptions from wrong answer patterns
- **Learning Prescriptions** — Phased remediation plans: Watch → Practice → Verify
- **Resource Curation** — Quality-scored recommendations from trusted sources (3Blue1Brown, Khan Academy) with specific timestamps
- **Soft Gates** — Students can skip ahead but get warned about missing prerequisites

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Chat Panel  │  │ Knowledge   │  │ Prescription Card       │ │
│  │             │  │ Graph Viz   │  │ (Watch→Practice→Verify) │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              LangGraph Agent Orchestrator                │   │
│  │   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────────┐  │   │
│  │   │ Lesson │ → │   QA   │ → │  Quiz  │ → │ Evaluate │  │   │
│  │   └────────┘   └────────┘   └────────┘   └──────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Knowledge   │  │ Student     │  │ Prescription Engine     │ │
│  │ Graph       │  │ Model (IRT) │  │ + Resource Curator      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Adaptive    │  │Misconception│  │ Socratic Tutor (LLM)    │ │
│  │ Tester      │  │ Detector    │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Redis (Session State)  │  GPT-4o-mini  │  Tavily (Search)     │
└─────────────────────────────────────────────────────────────────┘
```

## 🎓 Learning Flow

```
1. LESSON     → Student sees concept explanation
                ↓
2. Q&A        → Socratic tutor answers questions (guides, doesn't tell)
                ↓
3. QUIZ       → 3 progressive questions (Easy → Medium → Hard)
                ↓
4. EVALUATE   → Pass (2/3)? → Next concept
                Fail?       → Root cause analysis → Prescription
                ↓
5. PRESCRIPTION → Watch curated video → Practice problems → Verify
                ↓
6. REPEAT     → Until mastery achieved
```

## 🧠 Core Components

### Knowledge Graph
```
Vectors → Matrix Operations → Determinants → Inverse Matrix → Eigenvalues
```
- Prerequisite mapping with dependency DAG
- Root cause tracing when students fail advanced concepts
- Visual graph with mastery color coding (🟢 Mastered, 🔴 Weak, ⚪ Neutral)

### Adaptive Tester (CAT)
- **Maximum Information criterion** — Selects questions that maximize learning about student ability
- **Progressive difficulty** — Easy → Medium → Hard within each quiz
- **IRT-based scoring** — Item Response Theory for accurate ability estimation

### Misconception Detector
```json
{
  "pattern": "scalar_multiply_vectors",
  "description": "Student multiplies vector components instead of adding",
  "remediation": "Vector addition: add corresponding components"
}
```
- Maps wrong answers to specific misconceptions
- Provides targeted remediation strategies

### Socratic Tutor
- Context-aware prompts with concept data injection
- Adaptive tone based on mastery level:
  - Low mastery → "extra patient and encouraging"
  - High mastery → "peer-like and intellectually stimulating"
- Streak-based encouragement
- Never gives answers directly (guides with questions)

### Prescription Engine
```
📋 Learning Prescription for: Eigenvalues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Diagnosis: Confusion between eigenvalue (scalar) and eigenvector (direction)

📚 Your Learning Path:

Phase 1: 🎬 Watch
   3Blue1Brown - Eigenvectors and Eigenvalues
   https://youtube.com/watch?v=PFDu9oVAE-g (timestamp: 2:34)
   Duration: 5 min

Phase 2: ✏️ Practice
   Khan Academy - Eigenvalue Problems
   Duration: 10 min

Phase 3: ✅ Verify
   Take verification quiz (pass 2/3 to proceed)
```

### Resource Curator
Quality-scored trusted sources:
| Source | Quality Score |
|--------|---------------|
| 3Blue1Brown | 0.99 |
| Khan Academy | 0.95 |
| Professor Leonard | 0.92 |
| MIT OpenCourseWare | 0.92 |
| Organic Chemistry Tutor | 0.90 |

Features:
- YouTube search with timestamp extraction
- Tavily web search for articles/tutorials
- Difficulty-appropriate resource matching

## 🛠️ Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** — High-performance async API
- **LangGraph** — Multi-agent state machine orchestration
- **LangChain + GPT-4o-mini** — Socratic tutoring conversations
- **Redis** — Session state management
- **Tavily API** — Web search for resource curation

### Frontend
- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** — Cyberpunk-inspired dark theme
- **React Force Graph** — Knowledge graph visualization

## 📁 Project Structure

```
mahavihara/
├── api/
│   └── main.py              # FastAPI endpoints
├── core/
│   ├── knowledge_graph.py   # Concept DAG + prerequisites
│   ├── student_model.py     # IRT-based ability estimation
│   ├── adaptive_tester.py   # CAT implementation
│   └── misconception_detector.py
├── teaching/
│   ├── socratic_tutor.py    # LLM-based Socratic method
│   ├── prescription_engine.py
│   └── resource_curator.py  # YouTube + Tavily search
├── data/
│   ├── linear_algebra.json  # Concepts, lessons, questions
│   └── misconceptions/      # Wrong answer → misconception mappings
├── agent.py                 # LangGraph state machine
├── redis_store.py           # Session persistence
├── mahavihara-frontend/     # Next.js app
│   ├── app/
│   │   └── page.tsx         # Main chat + graph UI
│   └── components/
│       ├── KnowledgeGraph.tsx
│       └── PrescriptionCard.tsx
└── tests/
```

## 🚀 Installation

### Prerequisites
- Python 3.11+
- Node.js 20+
- Redis server
- OpenAI API key
- Tavily API key (optional, for resource search)

### Backend Setup

```bash
# Clone repository
git clone https://github.com/anuzzzzz/mahavihara.git
cd mahavihara

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
REDIS_URL=redis://localhost:6379
EOF

# Start Redis (if not running)
redis-server

# Run backend
uvicorn api.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd mahavihara-frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Visit `http://localhost:3000`

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/start-session` | POST | Initialize new tutoring session |
| `/chat` | POST | Send message, receive tutor response |
| `/graph-state/{session_id}` | GET | Get knowledge graph visualization data |
| `/prescription/{session_id}` | GET | Get current learning prescription |

## 🎯 Concepts Covered

| Concept | Prerequisites | Difficulty |
|---------|--------------|------------|
| Vectors | — | 0.3 |
| Matrix Operations | Vectors | 0.4 |
| Determinants | Matrix Ops | 0.5 |
| Inverse Matrix | Determinants | 0.6 |
| Eigenvalues | Inverse Matrix | 0.7 |

## 🔮 Future Improvements

- [ ] Expand to Calculus, Statistics, and other subjects
- [ ] Add voice interaction (Whisper ASR)
- [ ] Implement spaced repetition for long-term retention
- [ ] Deploy to cloud with persistent user accounts
- [ ] Add collaborative learning features

## 📄 License

MIT License

---

Built for hackathon by [Anuj Jokhani](https://github.com/anuzzzzz)
