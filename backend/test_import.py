import sys
print(sys.path)
try:
    import PIL
    print("PIL ok")
except ImportError as e:
    print(f"PIL error: {e}")
