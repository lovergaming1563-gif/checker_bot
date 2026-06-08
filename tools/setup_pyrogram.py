import asyncio
import os
import shutil
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

async def setup():
    print("🚀 Pyrogram Session Setup Utility")
    print("-" * 35)

    api_id = input("Enter your API_ID: ").strip()
    api_hash = input("Enter your API_HASH: ").strip()
    phone_number = input("Enter your Phone Number (with country code, e.g., +123456789): ").strip()

    client = Client(
        name="setup_session",
        api_id=int(api_id),
        api_hash=api_hash,
        in_memory=True
    )

    await client.connect()

    try:
        code_hash = await client.send_code(phone_number)
        print(f"\n✅ Login code sent to {phone_number}")
        
        phone_code = input("Enter the OTP code from Telegram: ").strip()
        
        try:
            await client.sign_in(phone_number, code_hash.phone_code_hash, phone_code)
        except SessionPasswordNeeded:
            password = input("2FA Password detected. Enter your 2FA password: ").strip()
            await client.check_password(password)

        session_string = await client.export_session_string()
        print("\n✅ Session generated successfully.")

        # Handle .env update
        env_file = ".env"
        backup_file = ".env.backup"

        if os.path.exists(env_file):
            shutil.copy(env_file, backup_file)
            print(f"✅ Created backup: {backup_file}")

        # Read existing .env content
        lines = []
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                lines = f.readlines()

        new_values = {
            "PYROGRAM_API_ID": api_id,
            "PYROGRAM_API_HASH": api_hash,
            "PYROGRAM_SESSION_STRING": session_string
        }

        # Update existing or add new
        updated_content = []
        keys_found = set()

        for line in lines:
            if "=" in line:
                key = line.split("=")[0].strip()
                if key in new_values:
                    updated_content.append(f"{key}={new_values[key]}\n")
                    keys_found.add(key)
                    continue
            updated_content.append(line)

        # Append missing keys
        for key, value in new_values.items():
            if key not in keys_found:
                if updated_content and not updated_content[-1].endswith("\n"):
                    updated_content.append("\n")
                updated_content.append(f"{key}={value}\n")

        with open(env_file, "w") as f:
            f.writelines(updated_content)

        print("✅ .env updated with Pyrogram credentials.")
        print("-" * 35)
        print("\nRestart the bot with:")
        print("python -m src.main")

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(setup())
