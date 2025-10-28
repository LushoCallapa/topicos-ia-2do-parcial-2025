# 🧠 AI DB Assistant

Un asistente inteligente capaz de responder **consultas en lenguaje natural** sobre una base de datos SQL.  
El sistema usa **FastAPI** como backend, **SQLite** como base de datos local y un **frontend web** estático integrado.

---

## 🚀 Características

- 🗣️ **Consultas en lenguaje natural** (ej. “¿Cuántos productos se vendieron este mes?”)  
- 🤖 **Agente LLM (dspy)** que traduce texto natural a SQL y genera respuestas amigables.  
- 🧩 **Base de datos SQLite** creada automáticamente con datos de ejemplo.  
- ⚡ **Consultas síncronas y asíncronas** (background tasks).  
- 💻 **Frontend web** incluido dentro del proyecto (`/frontend`), montado automáticamente por FastAPI.  
- 🌐 **CORS habilitado** para facilitar pruebas desde navegador o Postman.

---

## 🏗️ Estructura del proyecto

