from app import app, db
from sqlalchemy import text

def add_resume_text_column():
    """Adiciona a coluna resume_text se ela não existir"""
    with app.app_context():
        try:
            # Tenta adicionar a coluna
            with db.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE candidate ADD COLUMN IF NOT EXISTS resume_text TEXT"
                ))
                conn.commit()
            print("✅ Coluna resume_text adicionada com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao adicionar coluna (pode já existir): {e}")

if __name__ == "__main__":
    add_resume_text_column()
    