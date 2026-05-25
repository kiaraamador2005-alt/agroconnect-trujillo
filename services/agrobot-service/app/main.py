from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os

app = FastAPI()

# Modelo para recibir los mensajes del chat
class ChatMessage(BaseModel):
    message: str

# Interfaz HTML Profesional con Tailwind CSS
html_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgroConnect | Plataforma Inteligente</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 h-screen flex flex-col">
    <header class="bg-green-700 text-white p-4 shadow-lg">
        <h1 class="text-2xl font-bold">AgroConnect AI</h1>
    </header>
    
    <main class="flex-1 overflow-y-auto p-4 flex flex-col items-center">
        <div id="chat-container" class="w-full max-w-2xl bg-white rounded-lg shadow-md p-6 space-y-4">
            <div id="chat-box" class="space-y-3 h-96 overflow-y-auto border-b pb-4">
                <p class="text-gray-600"><b>AgroBot:</b> ¡Hola! Soy tu asistente agrícola inteligente. ¿En qué puedo ayudarte con tus cultivos hoy?</p>
            </div>
            <div class="flex gap-2">
                <input id="user-input" type="text" class="flex-1 border rounded p-2" placeholder="Escribe tu consulta...">
                <button onclick="sendMessage()" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">Enviar</button>
            </div>
        </div>
    </main>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const chatBox = document.getElementById('chat-box');
            if (!input.value) return;

            chatBox.innerHTML += `<p class="text-right"><b>Tú:</b> ${input.value}</p>`;
            
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input.value })
            });
            const data = await response.json();
            
            chatBox.innerHTML += `<p class="text-green-800"><b>AgroBot:</b> ${data.reply}</p>`;
            input.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return html_template

@app.post("/chat")
async def chat(data: ChatMessage):
    # Aquí es donde ocurre la magia de tu Agente IA
    # En un entorno profesional aquí llamarías a la API de OpenAI o Gemini
    user_msg = data.message.lower()
    if "plaga" in user_msg:
        reply = "Detecto preocupación por plagas. Te recomiendo revisar el estado de las hojas y aplicar un control preventivo biológico."
    elif "riego" in user_msg:
        reply = "Para el riego, asegúrate de medir la humedad del suelo a 10cm de profundidad. ¿Qué cultivo estás monitoreando?"
    else:
        reply = "Entiendo tu consulta sobre " + user_msg + ". Como AgroBot, estoy procesando los datos de tu base Neon para darte una respuesta técnica precisa."
    
    return {"reply": reply}
