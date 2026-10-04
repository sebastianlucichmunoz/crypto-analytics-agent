from src.agents.notification_agent import ejecutar_agente_notificaciones
from src.agents.email_sender import enviar_alertas_pendientes

if __name__ == "__main__":
    print("=== PASO 1: Ejecutando Agente de IA y guardando en MongoDB ===")
    ejecutar_agente_notificaciones()
    
    print("\n=== PASO 2: Procesando y enviando correos pendientes ===")
    enviar_alertas_pendientes()