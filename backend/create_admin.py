from database import SessionLocal
from models import User
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def create_admin():
    db = SessionLocal()

    try:
        print("\n=== Create Administrator Account ===\n")

        name = input("Enter administrator name: ").strip()
        email = input("Enter administrator email: ").strip().lower()

        if not name or not email:
            print("Error: Name and email cannot be empty.")
            return

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            print("Error: This email is already registered.")
            return

        # Password will be visible while typing.
        password = input("Enter administrator password: ")
        confirm_password = input("Confirm administrator password: ")

        if len(password) < 8:
            print("Error: Password must contain at least 8 characters.")
            return

        if password != confirm_password:
            print("Error: Passwords do not match.")
            return

        admin = User(
            name=name,
            email=email,
            password_hash=password_hash.hash(password),
            role="admin",
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\nAdministrator created successfully!")
        print(f"Name: {admin.name}")
        print(f"Email: {admin.email}")
        print(f"Role: {admin.role}")

    except Exception as error:
        db.rollback()
        print(f"Error creating administrator: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()