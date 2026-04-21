def safe_div(a, b):
    try:
        return a / b if b else None
    except:
        return None