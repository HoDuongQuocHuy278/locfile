def is_valid_number(value):
    try:
        int(value)
        return True
    except:
        return False


def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default