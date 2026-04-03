import os

def check_for_nulls(directory):
    corrupted_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                        if b'\x00' in data:
                            corrupted_files.append(path)
                except Exception as e:
                    print(f"Error reading {path}: {e}")
    return corrupted_files

if __name__ == "__main__":
    target = r"d:\loveable_app\react-to-android\backend"
    found = check_for_nulls(target)
    if found:
        print("CORRUPTED_FILES_START")
        for f in found:
            print(f)
        print("CORRUPTED_FILES_END")
    else:
        print("CLEAN")
