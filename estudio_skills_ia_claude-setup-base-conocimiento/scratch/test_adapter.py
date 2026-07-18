import os
import sys
from dotenv import load_dotenv

# Asegurar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.llm.groq_adapter import GroqICPAdapter

load_dotenv()

def test():
    adapter = GroqICPAdapter()
    
    # Simular una conversación acumulada
    inputs = [
        "Busco empresas en Colombia que usen Python y Django",
        "salud",
        "SaaS B2B"
    ]
    
    acumulado = []
    for i, inp in enumerate(inputs):
        acumulado.append(inp)
        combinado = ". ".join(acumulado)
        print(f"\n--- PASO {i+1} ---")
        print(f"Combinado enviado: {combinado}")
        try:
            manifiesto = adapter.analizar(combinado)
            print("OK Exito:")
            print(manifiesto.model_dump_json(indent=2))
        except ValueError as exc:
            print("ERROR Preguntas de clarificacion:")
            # Evitar emojis y caracteres no cp1252
            err_msg = str(exc).encode('ascii', errors='replace').decode('ascii')
            print(err_msg)

if __name__ == "__main__":
    test()
