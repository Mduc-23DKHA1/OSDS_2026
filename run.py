import subprocess
import sys
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UTILS_DIR = os.path.join(BASE_DIR, "utils")


def run_script(script_name):
    script_path = os.path.join(UTILS_DIR, script_name)

    print("\n" + "=" * 60)
    print(f"ĐANG CHẠY: {script_name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, script_path]
    )

    if result.returncode != 0:
        print(f"\n❌ {script_name} bị lỗi!")
        print("Pipeline đã dừng.")
        return False

    print(f"\n✅ {script_name} hoàn thành.")
    return True


def main():

    script_run_list = [
        "API_Categories.py",            # chạy API gọi json
        "Extract_categories.py",        # chạy Extract để chuyển json thành csv
        "Transform_categories_data.py"  # chạy Transform để tạo link
    ]
    
    for script in script_run_list:
        if not run_script(script):
            return

    print("\n" + "=" * 60)
    print("🎉 PIPELINE HOÀN THÀNH!")
    print("=" * 60)


if __name__ == "__main__":
    main()