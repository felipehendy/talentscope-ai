"""
Script para adicionar coluna linkedin_url na tabela candidate
Execute com: python add_linkedin_column.py
"""
import os
from app import app, db
from sqlalchemy import text

def add_linkedin_column():
    with app.app_context():
        try:
            # Verificar se a coluna já existe
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='candidate' AND column_name='linkedin_url'
            """))
            
            if result.fetchone():
                print("✅ Coluna linkedin_url já existe")
                return
            
            # Adicionar a coluna
            db.session.execute(text("""
                ALTER TABLE candidate 
                ADD COLUMN linkedin_url VARCHAR(500) NULL
            """))
            
            db.session.commit()
            print("✅ Coluna linkedin_url adicionada com sucesso!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")

if __name__ == '__main__':
    add_linkedin_column()