
from database import SessionLocal
from models import User
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def reset_password():
    db = SessionLocal()

    try:
        email = input("Enter admin email: ").strip().lower()

        admin = (
            db.query(User)
            .filter(
                User.email == email,
                User.role == "admin",
            )
            .first()
        )

        if admin is None:
            print("Administrator account not found.")
            return

        password = input("Enter new password: ")
        confirm = input("Confirm new password: ")

        if len(password) < 12:
            print("Password must contain at least 12 characters.")
            return

        if password != confirm:
            print("Passwords do not match.")
            return

        admin.password_hash = password_hash.hash(password)
        db.commit()

        print("Administrator password changed successfully.")

    except Exception as error:
        db.rollback()
        print(f"Error: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    reset_password()

