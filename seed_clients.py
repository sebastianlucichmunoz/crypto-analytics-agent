from src.db import get_db
from datetime import datetime

def seed_test_clients():
    db = get_db()
    db.clients.delete_many({})
    
    clientes_iniciales = [
        {
            "name": "Sebastian L",
            "email": "sebastianmartinlucich@gmail.com", 
            "watchlist": ["bitcoin", "ethereum"],
            "preferencia": "Me interesa cazar cualquier movimiento a corto plazo, avísame por cualquier cambio aunque sea pequeño.",
            "active": True,
            "created_at": datetime.utcnow()
        }, 
        {
            "name": "María Gómez",
            "email": "sebastianmarlucichmunoz@example.com",
            "watchlist": ["solana", "cardano"],
            "preferencia": "No me importan las pequeñas bajadas, solo quiero saber si mi moneda se desploma para vender a tiempo.",
            "active": True,
            "created_at": datetime.utcnow()
        }
    ]
    
    db.clients.insert_many(clientes_iniciales)
    print(f"¡Se han insertado {len(clientes_iniciales)} clientes de prueba en la colección 'clients'!")

if __name__ == "__main__":
    seed_test_clients()