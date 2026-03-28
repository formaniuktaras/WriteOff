from app.services.backup_service import BackupService


if __name__ == "__main__":
    path = BackupService().create_backup()
    print(f"Backup created: {path}")
