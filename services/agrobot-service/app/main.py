from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

# Esta es la interfaz de tu chat
html_content = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AgroBot AI</title>
    <style>
        body { font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }
        #chat { width: 100%; max-width: 500px; height: 300px; border: 1px solid #ccc; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
        input { width: 100%; max-width: 500px; padding: 10px; }
    </style>
</head>
<body>
    <h1>AgroBot IA</h1>
    <div id="chat"></div>
    <input type="text" id="userInput" placeholder="Escribe tu duda sobre cultivos...">
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('userInput');
        input.onkeypress = function(e) {
            if (e.key === 'Enter') {
                chat.innerHTML += '<p><b>Tú:</b> ' + input.value + '</p>';
                chat.innerHTML += '<p><b>AgroBot:</b> Estoy procesando tu duda técnica... (Conectando IA)</p>';
                input.value = '';
            }
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_page():
    return html_content
