"""Extracted runtime section from app_runtime.py lines 5655-5684.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

def clear_scanner_cache(cache_dir: Path):
    cache_dir.mkdir(exist_ok=True)

    errors = []

    for item in cache_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                try:
                    os.chmod(item, stat.S_IWRITE)
                except Exception:
                    pass
                item.unlink()

            elif item.is_dir():
                def on_rm_error(func, path, exc_info):
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception as e:
                        errors.append(f"{path}: {e}")

                shutil.rmtree(item, onerror=on_rm_error)

        except Exception as e:
            errors.append(f"{item}: {e}")

    return errors


