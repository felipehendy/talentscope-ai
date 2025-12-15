"""
Script para criar ou resetar usuário ADMIN no banco de dados.

EXECUÇÃO LOCAL:
    python create_admin.py

EXECUÇÃO EM PRODUÇÃO (Render):
    via Start Command ou manual (one-off)
"""

from app import app, db, User
from werkzeug.security import generate_password_hash, check_password_hash
import os


def create_admin():
    with app.app_context():

        # 🔐 Credenciais via variável de ambiente
        ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
        ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@talentscope.com")
        ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # fallback apenas para DEV

        if not ADMIN_PASSWORD:
            raise Exception("❌ ADMIN_PASSWORD não definida!")

        print("🔍 Verificando usuário admin...")

        existing_user = User.query.filter_by(username=ADMIN_USERNAME).first()

        if existing_user:
            print("⚠️ Usuário admin já existe")
            print(f"   ID: {existing_user.id}")
            print(f"   Email: {existing_user.email}")

            print("🔄 Resetando senha...")
            existing_user.password_hash = generate_password_hash(ADMIN_PASSWORD)
            existing_user.is_admin = True

            db.session.commit()
            print("✅ Senha resetada com sucesso!")

        else:
            print("🔧 Criando novo usuário admin...")

            admin = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                password_hash=generate_password_hash(ADMIN_PASSWORD),
                is_admin=True
            )

            try:
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuário admin criado com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar admin: {e}")
                return

        # 🔍 Verificação final
        user = User.query.filter_by(username=ADMIN_USERNAME).first()

        if not user:
            print("❌ ERRO CRÍTICO: Usuário não encontrado após commit!")
            return

        print("\n✅ VERIFICAÇÃO FINAL")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Admin: {user.is_admin}")

        senha_ok = check_password_hash(user.password_hash, ADMIN_PASSWORD)
        print(f"   Teste de senha: {'OK' if senha_ok else 'FALHOU'}")

        print("\n🔑 CREDENCIAIS ATIVAS")
        print(f"   Username: {ADMIN_USERNAME}")
        print(f"   Password: {'(definida via variável de ambiente)'}")


if __name__ == "__main__":
    create_admin()
