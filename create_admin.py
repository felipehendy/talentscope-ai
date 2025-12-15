"""
Script para criar usuário admin direto no banco
EXECUTE: python create_admin.py
"""
from app import app, db, User
from werkzeug.security import generate_password_hash

def create_admin():
    with app.app_context():
        # Verificar se já existe usuário
        existing_user = User.query.filter_by(username='admin').first()
        
        if existing_user:
            print(f"⚠️  Usuário 'admin' já existe!")
            print(f"   Email: {existing_user.email}")
            print(f"\n🔄 Resetando senha...")
            
            existing_user.password_hash = generate_password_hash('admin123')
            db.session.commit()
            
            print(f"✅ Senha resetada!")
        else:
            print("🔧 Criando novo usuário admin...")
            
            # Criar usuário
            admin = User(
                username='admin',
                email='admin@talentscope.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            
            try:
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuário admin criado com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar usuário: {e}")
                return
        
        # Verificar se foi salvo corretamente
        user = User.query.filter_by(username='admin').first()
        
        if user:
            print(f"\n✅ Verificação OK!")
            print(f"   ID: {user.id}")
            print(f"   Username: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Admin: {user.is_admin}")
            print(f"   Hash válido: {user.password_hash.startswith('scrypt:') or user.password_hash.startswith('pbkdf2:')}")
            
            print(f"\n🔑 CREDENCIAIS PARA LOGIN:")
            print(f"   Username: admin")
            print(f"   Password: admin123")
            
            # Testar hash
            from werkzeug.security import check_password_hash
            senha_ok = check_password_hash(user.password_hash, 'admin123')
            print(f"\n✅ Teste de senha: {'OK' if senha_ok else 'FALHOU'}")
        else:
            print("❌ Erro: Usuário não foi salvo no banco!")

if __name__ == '__main__':
    create_admin()