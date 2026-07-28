# Interview Simulator

AI-powered mock interview platform that generates role-specific technical questions, evaluates answers in real-time, and tracks progress over time.

## Features

- **Adaptive questions** — generated based on your profile, target role, and past performance
- **Code execution** — write and run code in a sandboxed environment, validated against test cases
- **Real-time evaluation** — LLM scores answers on correctness, depth, and communication
- **Progress tracking** — per-topic scoring with round-by-round reports
- **Text-to-speech** — questions read aloud for realistic interview feel
- **Research mode** — scrape job postings to tailor questions to specific roles

## Stack

- **Backend:** FastAPI + Pydantic
- **LLM:** Claude (Sonnet) for question generation and evaluation
- **Code sandbox:** Isolated subprocess execution with memory/time limits
- **TTS:** macOS `say` command
