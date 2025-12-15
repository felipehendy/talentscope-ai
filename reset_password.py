# ==================== SCRIPT DE CORREÇÃO ====================
# EXECUTE ESTE SCRIPT PARA RESETAR A SENHA DO USUÁRIO

from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Buscar primeiro usuário
    user = User.query.first()
    
    if user:
        print(f"Usuário encontrado: {user.username}")
        print(f"Hash atual: {user.password_hash[:50]}...")
        
        # Gerar novo hash correto
        nova_senha = "admin123"  # ← MUDE AQUI PARA SUA SENHA
        user.password_hash = generate_password_hash(nova_senha)
        
        db.session.commit()
        
        print(f"\n✅ Senha resetada com sucesso!")
        print(f"Novo hash: {user.password_hash[:50]}...")
        print(f"\n🔑 Use estas credenciais:")
        print(f"   Username: {user.username}")
        print(f"   Password: {nova_senha}")
    else:
        print("❌ Nenhum usuário encontrado no banco!")
        print("\n💡 Crie um usuário primeiro acessando /register")